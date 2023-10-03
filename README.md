# Data Tool Tranimitter

![DTT-Demo](https://user-images.githubusercontent.com/6131212/272154864-3e8cdf05-a80b-46f2-8019-f9aed5ee74c1.gif)

This application will use a UDP port to receive data from PS5 and insert the data into InfluxDB. The data can be visualized in Grafana.

Currently works for GT7, but I intend to add multigame support for iRacing and F1-202X.

I have been tracking telemetry data from multiple racing sims for some time. Multiple applications shipping data and separate storage are cumbersome to keep up and maintain. I want to create a centralized way in my home lab to ship data from multiple racing sims and store them in a time series database (TSDB).

## Deployment

1. Copy `.example.env` to `.env` and update variables as needed
1. `docker compose up -d` to run a InfluxDB, Grafana and Data tool transmission
1. If you have an exisiting InfluxDB or Grafana instance `docker compose -f app.docker-compose.yaml up -d`

## Notes

- Telemetry will record when AI is running laps in paused or background.
- Default InfluxDB bucket setttings is set to retain for 90 days
- (Optinal) Set a static IP on your PS5

## Credits

- Thank you to [Bornhall](https://github.com/Bornhall/) for their foundational work on [gt7telemetry](https://github.com/Bornhall/gt7telemetry). My contributions are built on their shoulders, and I am grateful for their dedication and work.
