# EVTX EventData Parser for Timesketch

## Overview
I was tired of not being able to query for fields when I was working on event logs into timesketch.
I might improve the parser ofor other kinds of event, but his one is at least working for evtx.

The script (`evtx_parser_enriched.py`) extracts and parses **EventData** fields embedded as XML strings within the `extra` column of `l2tcsv` files, and appends them as new columns. It also enriches the `datetime` column with the `timestamp_desc` value while keeping both fields intact.

The result is a fully enriched CSV file ready for import into Timesketch, providing structured visibility into individual event attributes directly extracted from `.evtx` files.

---

## 🧩 Workflow Summary
The complete process consists of three main stages:

### 1️⃣ Generate the `.plaso` file
Use **log2timeline.py** to create a Plaso timeline database from your EVTX logs. 

```bash
log2timeline.py Microsoft-Windows-Sysmon-Operational.evtx -storage_file logs.plaso
```
This will generate a `.plaso` file:
```
logs.plaso
```

### 2️⃣ Convert `.plaso` to `.csv`
Use **psort.py** to convert the Plaso file into CSV (l2tcsv format):

```bash
psort.py -o l2tcsv -w output.csv logs.plaso
```

This CSV will include an `extra` column containing XML fragments (`xml_string`) for each event.

### 3️⃣ Parse and Enrich the CSV
Run the EVTX parser to extract structured EventData fields and enrich the `datetime` column:

```bash
python3 evtx_parser.py output.csv output_enriched.csv
```

This generates `output_enriched.csv`, ready for import into **Timesketch**.

---

## ⚙️ Main Features
- Extracts XML EventData from the `extra` column.
- Parses all `<Data Name="...">` fields within EventData.
- Automatically prefixes each field with its `EventID` (e.g., `4688_SubjectUserSid`).
- Adds `event_id` and `xml_string` as additional fields.
- Renames key Plaso columns for Timesketch compatibility:
  - `date` → `datetime`
  - `time` → `timestamp_desc`
  - `desc` → `message`
- Enriches the `datetime` field by appending the corresponding `timestamp_desc` value.

---

## 🧠 Key Functions

### `extract_xml_from_extra(extra_field: str)`
Searches the `extra` column to extract the XML block following `xml_string:`.

### `extract_event_id_from_xml(xml_string: str)`
Parses the XML to retrieve the `<EventID>` value.

### `parse_event_data(xml_string: str, event_id: str)`
Extracts all key/value pairs within `<EventData>` and labels them as `EventID_FieldName`.

### `process_csv(input_file: str, output_file: str, verbose: bool = False)`
The main function that reads the input CSV, applies parsing, enriches the fields, and writes the output enriched CSV.

---

---

## 🧰 Requirements
- Python 3.x
- Plaso (log2timeline, psort)

Install Plaso if not already installed:
```bash
sudo apt install plaso-tools
```

---

## 🧪 Example Full Workflow
```bash
# Step 1: Generate .plaso file from EVTX
log2timeline.py Microsoft-Windows-Sysmon-Operational.evtx -storage_file logs.plaso

# Step 2: Convert .plaso to CSV
psort.py -o l2tcsv -w output.csv logs.plaso

# Step 3: Enrich CSV with EVTX parser
python3 evtx_parser.py output.csv output_enriched.csv

# Step 4: Import into Timesketch
Upload `output_enriched.csv` to your Timesketch instance.
```

---

## ✅ Result
After completion, you’ll have a **Timesketch-ready enriched CSV** that contains:
- Original Plaso fields.
- Enriched and parsed XML data from EVTX.
- Example from a HTB sherlock : 

  <img width="915" height="524" alt="Screenshot from 2025-10-25 07-52-11" src="https://github.com/user-attachments/assets/b35bca28-09c3-4b7f-97c5-d4d0d34959c4" />



---

**Author:** Rastipnwer  
**Version:** 1.0.0  
**License:** Apache 2.0

