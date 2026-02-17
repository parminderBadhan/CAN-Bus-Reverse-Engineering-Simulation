# CAN Project Replay System

This project is designed to simulate and replay CAN (Controller Area Network) bus data for reverse engineering and analysis purposes. It provides a simple environment to log, analyze, and replay CAN messages, making it useful for automotive research, diagnostics, and educational demonstrations.

## Features
- Replay CAN bus data from log files
- Dockerized setup for easy deployment
- Example speed log included

## Getting Started

### Prerequisites
- Docker
- Python 3.x
- Git

### Setup
1. Clone this repository:
   ```sh
   git clone https://github.com/parminderBadhan/CAN-Bus-Reverse-Engineering-Simulation.git
   cd CAN-Bus-Reverse-Engineering-Simulation
   ```
2. Build and run with Docker Compose:
   ```sh
   docker-compose up --build
   ```
3. Alternatively, run the Python script directly:
   ```sh
   python main.py
   ```

## Files
- `main.py` — Main script for replaying CAN data
- `speed_log.csv` — Example CAN bus log file
- `Dockerfile` — Docker image definition
- `docker-compose.yml` — Docker Compose configuration

## Usage
- Modify `speed_log.csv` to use your own CAN data logs.
- Adjust `main.py` as needed for your specific replay or analysis requirements.

## License
This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## Author
Parminder Badhan
