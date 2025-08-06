import pandas as pd
from datetime import datetime, timedelta
import requests # Import the requests library
import os
from dotenv import load_dotenv
import time # Import the time library for timing
load_dotenv()

# --- CONFIGURATION ---
# Updated to match your specific file and column names.

# The path to your CSV file.
CSV_FILE_PATH = r"C:\Users\cballow\Documents\GitHub\AmazonDailyIdlePerformanceWorkflow\data.csv"

# Your Slack webhook URL. Paste the NEW URL from your Slack App here.
SLACK_WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# The exact column names from your CSV file.
DATE_COLUMN = "Start Time (Local)"
SHIFT_COLUMN = "Shift Code"
EMPLOYEE_COLUMN = "Driver"
IDLE_TIME_COLUMN = "Idle Time"

# The hour at which a shift is considered a "late shift" for special filtering (e.g., 20 for 8 PM)
LATE_SHIFT_START_HOUR = 20
# Updated benchmark idle time
BENCHMARK_IDLE_TIME = 0.68


# --- HELPER FUNCTION FOR FORMATTING ---

def get_impact_emoji(idle_impact):
    """Returns a color-coded emoji based on the Idle Impact value."""
    if idle_impact >= 20:
        return '🔴'  # Very Bad
    elif idle_impact >= 10:
        return '🟠'  # Bad
    elif idle_impact >= 0:
        return '🟡'  # Fine
    else: # Less than 0
        return '🟢'  # Great

def get_site_average_emoji(site_average):
    """Returns a color-coded emoji based on the site-wide average idle time."""
    # Updated logic based on new thresholds
    if site_average > 1.35:
        return '🔴' # Very Bad
    elif site_average > 1.00:
        return '🟠' # Bad
    elif site_average >= 0.68:
        return '🟡' # Fine
    else: # Less than 0.68
        return '🟢' # Great

def format_for_slack(df, headers=["Status", "Driver", "Avg Idle Time", "% of Moves", "Idle Impact"]):
    """
    Takes a DataFrame and formats it into a text-based table string
    with borders, suitable for a Slack code block.
    """
    # Create a copy to avoid modifying the original DataFrame
    df_display = df.copy()

    # Format the numeric columns into nice strings for display
    df_display["Avg Idle Time"] = df_display["Avg Idle Time"].map('{:.2f}'.format)
    df_display["% of Moves"] = df_display["% of Moves"].map('{:.1%}'.format) # Formats as percentage
    df_display["Idle Impact"] = df_display["Idle Impact"].map('{:+.2f}'.format) # Shows + or - sign

    # Add a space to the emoji to help with monospace alignment before calculating width
    df_display["Status"] = df_display["Status"] + ' '

    # Determine the maximum width needed for each column
    col_widths = {col: max(df_display[col].astype(str).apply(len).max(), len(col)) for col in df_display.columns}

    separator = "+-" + "-+-".join(['-' * col_widths[col] for col in df_display.columns]) + "-+"
    header_line = "| " + " | ".join([col.ljust(col_widths[col]) for col in df_display.columns]) + " |"

    table_lines = [separator, header_line, separator]

    for _, row in df_display.iterrows():
        row_values = [str(row[col]).ljust(col_widths[col]) for col in df_display.columns]
        table_lines.append("| " + " | ".join(row_values) + " |")

    table_lines.append(separator)

    return "\n".join(table_lines)

def format_summary_box(summary_parts):
    """Takes a list of strings and wraps them in a formatted text box."""
    max_width = max(len(line) for line in summary_parts)
    separator = "+-" + "-" * max_width + "-+"

    boxed_lines = [separator]
    for line in summary_parts:
        boxed_lines.append(f"| {line.ljust(max_width)} |")
    boxed_lines.append(separator)

    return "\n".join(boxed_lines)


# --- SCRIPT LOGIC ---

def analyze_day_performance(file_path, target_day_str):
    """
    Loads data, filters for activity on a specific day (including work from
    the previous day's late shifts), and sends a formatted report.
    """
    try:
        overall_start_time = time.time()
        print("Starting the daily report workflow...")

        # --- Data Reading and Processing ---

        print("\nStep 1: Reading CSV file...")
        step_time = time.time()
        df = pd.read_csv(file_path)
        print(f"-> Done. Read {len(df)} rows in {time.time() - step_time:.2f} seconds.")

        print("\nStep 2: Converting date column...")
        step_time = time.time()
        df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])
        print(f"-> Done. Converted dates in {time.time() - step_time:.2f} seconds.")

        print("\nStep 3: Cleaning shift codes...")
        step_time = time.time()
        df['Cleaned Shift'] = df[SHIFT_COLUMN].str.split('-').str[-1]
        print(f"-> Done. Cleaned shifts in {time.time() - step_time:.2f} seconds.")

        print("\nStep 4: Filtering for all activity on the target day...")
        step_time = time.time()

        target_date = pd.to_datetime(target_day_str).date()

        activity_on_target_day = df[df[DATE_COLUMN].dt.date == target_date].copy()
        print(f"-> Done. Found {len(activity_on_target_day)} activities on {target_day_str} in {time.time() - step_time:.2f} seconds.")

        if activity_on_target_day.empty:
            message = f"No data found for the date: {target_day_str}"
            print(message)
            send_to_slack(message)
            return

        total_daily_moves = len(activity_on_target_day)
        site_average = activity_on_target_day[IDLE_TIME_COLUMN].mean()

        activity_on_target_day['Reporting Shift'] = activity_on_target_day['Cleaned Shift']

        try:
            overnight_condition = (activity_on_target_day[DATE_COLUMN].dt.hour < 5) & \
                                  (pd.to_numeric(activity_on_target_day['Cleaned Shift']) >= LATE_SHIFT_START_HOUR * 100)
            activity_on_target_day.loc[overnight_condition, 'Reporting Shift'] = activity_on_target_day['Cleaned Shift'] + ' (Overnight)'
        except Exception:
            print("Could not apply overnight logic, continuing with standard shifts.")
            pass

        all_shifts_in_report = activity_on_target_day['Reporting Shift'].unique()

        def shift_sort_key(shift_name):
            if '(Overnight)' in shift_name:
                return f"0_{shift_name}"
            else:
                return f"1_{shift_name}"

        sorted_shifts = sorted(all_shifts_in_report, key=shift_sort_key)
        print(f"\nFound data for shifts: {sorted_shifts}")

        # --- Build the Slack Message ---
        print("\nStep 5: Building the Slack message...")

        # Main message title
        message_parts = []
        formatted_date = pd.to_datetime(target_day_str).strftime('%A, %B %d')
        message_parts.append(f"📊 *Daily Idling Time Report for {formatted_date}*")

        # Add Site Average and Benchmark (bolded labels)
        site_status_emoji = get_site_average_emoji(site_average) # Uses special logic for site average
        difference = site_average - BENCHMARK_IDLE_TIME
        message_parts.append(f"\n*Site-wide Daily Average:* {site_average:.2f} {site_status_emoji}")
        message_parts.append(f"*Benchmark:* {BENCHMARK_IDLE_TIME:.2f} (Difference: {difference:+.2f})")

        # --- Create a formatted summary block ---
        summary_parts = []
        idle_impact_key = (
            "Idle Impact Key:  (Impact = (Avg Idle - Benchmark) * Moves)",
            "  🟢 Great:    < 0",
            "  🟡 Fine:     0 to 10",
            "  🟠 Bad:      10 to 20",
            "  🔴 Very Bad:  20+"
        )
        summary_parts.extend(idle_impact_key)
        summary_parts.append("") # Add a blank line for spacing

        summary_parts.append("Top 5 Highest Idle Time Incidents")
        top_5 = activity_on_target_day.nlargest(5, IDLE_TIME_COLUMN)
        for _, row in top_5.iterrows():
            incident_time = row[DATE_COLUMN].strftime('%H:%M')
            driver = row[EMPLOYEE_COLUMN]
            idle_time = row[IDLE_TIME_COLUMN]
            summary_parts.append(f"  - {driver}: {idle_time:.2f} at {incident_time}")

        summary_block = format_summary_box(summary_parts)
        message_parts.append(f"```{summary_block}```") # Wrap summary in a code block

        # Generate the report string for each shift
        all_shift_reports = []
        for shift_name in sorted_shifts:
            shift_activity = activity_on_target_day[activity_on_target_day['Reporting Shift'] == shift_name].copy()
            shift_summary = shift_activity.groupby(EMPLOYEE_COLUMN).agg(
                Avg_Idle_Time=(IDLE_TIME_COLUMN, 'mean'),
                Move_Count=(IDLE_TIME_COLUMN, 'size')
            )
            shift_summary['% of Moves'] = shift_summary['Move_Count'] / total_daily_moves
            # REVERTED LOGIC: Compare to the fixed BENCHMARK_IDLE_TIME
            shift_summary['Idle Impact'] = (shift_summary['Avg_Idle_Time'] - BENCHMARK_IDLE_TIME) * shift_summary['Move_Count']
            shift_summary.insert(0, "Status", shift_summary["Idle Impact"].apply(get_impact_emoji))
            shift_summary = shift_summary.sort_values('Idle Impact') # Sort by the new Idle Impact
            shift_summary.rename(columns={'Avg_Idle_Time': 'Avg Idle Time'}, inplace=True)
            shift_summary.reset_index(inplace=True)

            display_shift = shift_name.replace(' (Overnight)', '')
            formatted_shift = f"{display_shift[:2]}:{display_shift[2:]}"

            shift_report_parts = []
            if '(Overnight)' in shift_name:
                shift_report_parts.append(f"\n*{formatted_shift}* (from previous day)")
            else:
                shift_report_parts.append(f"\n*{formatted_shift}*")

            if shift_summary.empty:
                shift_report_parts.append("No employee data to analyze for this shift.")
            else:
                table_str = format_for_slack(shift_summary[['Status', 'Driver', 'Avg Idle Time', '% of Moves', 'Idle Impact']])
                shift_report_parts.append(f"```{table_str}```")

            all_shift_reports.append("\n".join(shift_report_parts))

        # --- Find split point and send messages ---
        split_index = -1
        for i, shift_name in enumerate(sorted_shifts):
            cleaned_shift = shift_name.split(' ')[0]
            try:
                if int(cleaned_shift) < 600: # Split after shifts starting before 6 AM
                    split_index = i
            except ValueError:
                continue

        if split_index == -1 or split_index == len(all_shift_reports) - 1:
            final_message = "\n".join(message_parts) + "".join(all_shift_reports)
            send_to_slack(final_message)
        else:
            message_1_shifts = all_shift_reports[:split_index + 1]
            final_message_1 = "\n".join(message_parts) + "".join(message_1_shifts)
            send_to_slack(final_message_1)

            time.sleep(1) # Pause for a second before sending the next part

            message_2_shifts = all_shift_reports[split_index + 1:]
            final_message_2 = "📊 *Daily Idling Time Report (continued)*\n" + "".join(message_2_shifts)
            send_to_slack(final_message_2)

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        send_to_slack(f"An unexpected error occurred in the daily report: {e}")


def send_to_slack(message):
    """Sends a message to the configured Slack webhook."""
    if "YOUR_NEW_SLACK_APP_WEBHOOK_URL_HERE" in SLACK_WEBHOOK_URL:
        print("\nWARNING: Slack webhook URL is not set. Skipping notification.")
        return

    try:
        payload = {"text": message}
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=30)
        if response.status_code == 200:
            print(f"-> Done. Successfully sent report to Slack!")
        else:
            print(f"-> Error sending to Slack. Status Code: {response.status_code}, Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"-> Error connecting to Slack: {e}")


# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y-%m-%d')

    # Always run the daily report
    print(f"Automatically running analysis for yesterday: {yesterday_str}")
    analyze_day_performance(CSV_FILE_PATH, yesterday_str)
