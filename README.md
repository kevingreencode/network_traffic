## 🧱 1. Project Overview

The purpose of the project is to transform raw PCAP files (captured from multiple switches in a network topology) into structured, queryable data. This data is stored in a MySQL database, enabling easier analytics via SQL instead of parsing unstructured logs.

---

## 🔧 2. Key Components

### a. PCAP Ingestion Module

- **Role:** Parses PCAP files and converts them into structured records (e.g., timestamp, source IP, destination IP, protocol, packet size, etc.).
- **Tools used:** Python with libraries like `tshark`.
- **Flow:**
  - Accepts a directory of PCAP files (e.g., one per switch).
  - Extracts key packet-level metadata.
  - Associates each packet with its originating switch (based on filename).
  - Prepares the data for insertion into MySQL.

---

### b. Data Storage Layer

- **Database:** MySQL
- **Schema design:**
  - `switches` table: metadata about switches (ID, name, location).
  - `packets` table: each row is a parsed packet, with a foreign key to `ports` and `switches`.
    - Columns include timestamp, source IP, destination IP, protocol, port, length, etc.

---

### c. ETL Manager (Extract, Transform, Load)

- **Role:** Orchestrates parsing, transformation, and loading.
- **Features:**
  - Handles bulk insertion to minimize latency.
  - Logs import errors and supports reprocessing failed files.
  - TODO: Support incremental ingestion (new PCAPs).

---

### d. Query and Analytics Layer

- **Role:** Enables users to run SQL queries to answer networking questions.
- **Examples of use cases:**
  - Find top talkers (most packets sent/received).
  - Detect traffic bottlenecks per switch or link.
  - Filter for specific protocols (e.g., TCP, ICMP).
- **Tools:** Web app (Flask)

---

### e. Frontend / Dashboard

- **Purpose:** Provides a UI for browsing packets, visualizing trends (TODO: Build custom queries).
- **Technology:** Flask with simple HTML/JS front-end or charts (Chart.js).

---

## 🔒 3. Security and Access

- Database credentials stored in environment variables or `config.py` file.
- PCAP data is sensitive—ensure encrypted transport (SSH) and secure storage.

---

## 🔁 4. Workflow

1. Place PCAP files (per switch) in a watched directory.
2. Python loader.py script runs.
3. Parsed packets are inserted into MySQL.
4. Query the data via SQL.
5. Insights and patterns are extracted efficiently across the entire topology.
