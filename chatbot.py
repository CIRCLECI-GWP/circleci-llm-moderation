#!/usr/bin/env python3

import os
import subprocess
from datetime import datetime

from openai import OpenAI

def record_flagged_content(offending_text: str):
    """
    Writes a small file indicating flagged content, then commits + pushes it
    to your GitHub repo. CircleCI picks up this commit and runs the pipeline,
    which can fail if it sees any flagged files.
    
    Requirements:
      - Git must be configured in this local environment with credentials or SSH.
      - You have a local clone of the repository that CircleCI monitors.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"flagged_event_{timestamp}.txt"

    with open(filename, "w") as f:
        f.write(f"Flagged content detected at {timestamp}\nOffending text:\n{offending_text}\n")

    try:
        # Stage and commit
        subprocess.run(["git", "add", filename], check=True)
        subprocess.run(["git", "commit", "-m", f"Add flagged content file {filename}"], check=True)

        # Push to main (ensure 'main' matches your default branch)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print(f"Pushed flagged file {filename} to repo, triggering CircleCI pipeline.")
    except subprocess.CalledProcessError as e:
        print(f"Error pushing flagged content file: {e}")

def initialize_openai_client():
    """
    Reads OPENAI_API_KEY from your environment (or sets it directly)
    and returns an OpenAI client instance for the 1.0+ interface.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set.")
    
    return OpenAI(api_key=api_key)

def moderate_text(client: OpenAI, text: str) -> bool:
    """
    Checks text against the Moderation endpoint.
    Returns True if flagged (disallowed), otherwise False.
    """
    try:
        response = client.moderations.create(input=text)
        return response.results[0].flagged
    except Exception as e:
        print(f"Moderation API error: {e}")
        # Default to flagged or handle differently
        return True

def run_chatbot():
    """
    A console-based chatbot using GPT-3.5-Turbo.
    We moderate BOTH the user's input and the model's output.
    If any is flagged, we block and commit/push a 'flagged_event' file
    so CircleCI fails the build on the next run.
    """
    client = initialize_openai_client()

    print("\n=== GPT-3.5-Turbo Chatbot (Moderate User & Model, then Commit Flagged File) ===")
    print("Type 'exit' or 'quit' to end the session.\n")

    messages = [
        {"role": "system", "content": "You are a helpful assistant specialized in technology topics."}
    ]

    while True:
        user_input = input("User: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Assistant: Goodbye!")
            break

        # 1) Moderate the user's input
        user_flagged = moderate_text(client, user_input)
        if user_flagged:
            print("Assistant: [User content flagged by moderation. Not processed.]")
            record_flagged_content(user_input)
            continue  # Skip sending to the model

        # If user input is safe, add to conversation
        messages.append({"role": "user", "content": user_input})

        try:
            # 2) Get model response
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=150
            )

            assistant_reply = response.choices[0].message.content.strip()

            # 3) Moderate the model's output
            model_flagged = moderate_text(client, assistant_reply)
            if model_flagged:
                print("Assistant: [Model output flagged by moderation. Not displayed.]")
                messages.append({"role": "assistant", "content": "[Blocked content]"})
                record_flagged_content(assistant_reply)
            else:
                print(f"Assistant: {assistant_reply}\n")
                messages.append({"role": "assistant", "content": assistant_reply})

        except Exception as e:
            print(f"Error: {e}")
            break

if __name__ == "__main__":
    run_chatbot()
