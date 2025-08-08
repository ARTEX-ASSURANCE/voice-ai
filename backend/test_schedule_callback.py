import asyncio
from dotenv import load_dotenv
import os
from tools import schedule_callback
from livekit.agents import RunContext

async def main():
    # Load environment variables from .env file
    load_dotenv()

    # Check if necessary environment variables are set
    if not os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE") or not os.getenv("GOOGLE_CALENDAR_ID"):
        print("Error: GOOGLE_SERVICE_ACCOUNT_FILE and GOOGLE_CALENDAR_ID must be set in your .env file.")
        print("Please create a service account, share your calendar with it, and update the .env file.")
        return

    # Create a mock RunContext
    context = RunContext()

    # --- Call the tool with test data ---
    customer_id = "TEST-12345"
    # Schedule for 2 minutes from now
    from datetime import datetime, timedelta
    schedule_time = datetime.now() + timedelta(minutes=2)
    datetime_str = schedule_time.isoformat()
    reason = "Test callback scheduled by test script"

    print(f"Attempting to schedule callback for customer '{customer_id}' at {datetime_str}...")

    result = await schedule_callback(
        context=context,
        customer_id=customer_id,
        datetime_str=datetime_str,
        reason=reason
    )

    print("\\n--- RESULT ---")
    print(result)
    print("--------------")
    print("\\nPlease check your Google Calendar to confirm the event was created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
