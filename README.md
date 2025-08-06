# Amazon Daily Idle Performance Workflow

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
![Version](https://img.shields.io/badge/version-1.0.0-informational)

Main project built for amazon internal middle mile network using python, (pandas), AWS QuickSight, Task Scheduler (on windows), and Slack API. Used to display live idle times to Managers while idle time accumulates from associates in the site yard.

---


## Features

- **Automated Daily Reporting:** Automatically calculates and sends daily idle time summaries directly to a designated Slack channel.
- **Efficient Data Processing:** Leverages the pandas library to efficiently process and aggregate associate activity logs.
- **Seamless Slack Integration:** Posts updates and reports using Slack webhooks, ensuring timely team communication.
- **Actionable Insights:** Provides clear summaries of idle periods to help monitor team availability and productivity.
- **Consistent & Reliable:** The automated script ensures tracking and reporting are performed consistently every day without manual intervention.

## Prereqs

- An active AWS Account with appropriate permissions.
- [AWS CLI](https://aws.amazon.com/cli/) configured on your local machine.
- [Python 3.8+](https://www.python.org/downloads/) with `pip`.
- Task scheduler for local automation.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/AmazonDailyIdlePerformanceWorkflow.git](https://github.com/your-username/AmazonDailyIdlePerformanceWorkflow.git)
    cd AmazonDailyIdlePerformanceWorkflow
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    
## Contributing

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/crazyStuff`)
3.  Commit your Changes (`git commit -m 'Add some nice addittions'`)
4.  Push to the Branch (`git push origin feature/wwwwwwwww`)
5.  Open a Pull Request

## License

MIT License.
