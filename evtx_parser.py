#!/usr/bin/env python3
"""
EVTX EventData Parser for Timesketch
Parses xml_string from the 'extra' field in l2tcsv format
Creates individual columns for each EventData field with naming convention: {EventID}_{FieldName}

"""

import csv
import xml.etree.ElementTree as ET
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional
import argparse


def extract_xml_from_extra(extra_field: str) -> Optional[str]:
    """
    Extract xml_string value from the extra field.
    The extra field contains key-value pairs like: key1: value1; key2: value2; xml_string: <xml>...</xml>

    Args:
        extra_field: The extra column content from l2tcsv

    Returns:
        XML string or None if not found
    """
    if not extra_field:
        return None

    # Look for xml_string: followed by XML content
    # The pattern captures everything after "xml_string: " until the end or next semicolon at root level
    match = re.search(r'xml_string:\s*(<Event\s+xmlns=.*?</Event>)', extra_field, re.DOTALL)

    if match:
        return match.group(1)

    return None


def extract_event_id_from_extra(extra_field: str) -> Optional[str]:
    """
    Extract event ID from extra field as fallback.

    Args:
        extra_field: The extra column content from l2tcsv

    Returns:
        Event ID string or None
    """
    if not extra_field:
        return None

    match = re.search(r'message_identifier:\s*(\d+)', extra_field)
    if match:
        return match.group(1)

    return None


def extract_event_id_from_short(short_field: str) -> Optional[str]:
    """
    Extract event ID from the short field which typically starts with [EventID / 0xHex].

    Args:
        short_field: The short column content

    Returns:
        Event ID string or None
    """
    if not short_field:
        return None

    match = re.match(r'\[(\d+)\s*/\s*0x[0-9a-fA-F]+\]', short_field)
    if match:
        return match.group(1)

    return None


def extract_event_id_from_xml(xml_string: str) -> Optional[str]:
    """
    Extract Event ID directly from the XML <EventID> tag.

    Args:
        xml_string: XML string containing Event element

    Returns:
        Event ID string or None
    """
    if not xml_string:
        return None

    try:
        root = ET.fromstring(xml_string)

        # Find EventID element in System section
        event_id_elem = root.find('.//{*}EventID')
        if event_id_elem is None:
            event_id_elem = root.find('.//EventID')

        if event_id_elem is not None and event_id_elem.text:
            return event_id_elem.text.strip()

    except Exception:
        pass

    return None


def parse_event_data(xml_string: str, event_id: str) -> Dict[str, str]:
    """
    Parse EventData XML and return dictionary with prefixed field names.

    Args:
        xml_string: XML string containing EventData
        event_id: Event ID to use as prefix

    Returns:
        Dictionary with keys like "4688.SubjectUserSid"
    """
    parsed_fields = {}

    if not xml_string or xml_string.strip() == '':
        return parsed_fields

    try:
        # Parse the XML
        root = ET.fromstring(xml_string)

        # Find EventData element (handle different namespaces)
        event_data = root.find('.//{*}EventData')
        if event_data is None:
            event_data = root.find('.//EventData')

        if event_data is not None:
            # Extract all Data elements
            for data_elem in event_data.findall('.//{*}Data'):
                name = data_elem.get('Name')
                value = data_elem.text if data_elem.text is not None else ''

                if name:
                    # Create prefixed field name: EventID.FieldName
                    field_key = f"{event_id}_{name}"
                    parsed_fields[field_key] = value

    except ET.ParseError as e:
        # If XML parsing fails, silently skip
        pass
    except Exception as e:
        # Catch any other exceptions
        pass

    return parsed_fields


def process_csv(input_file: str, output_file: str, verbose: bool = False):
    """
    Process CSV file and enrich with parsed EventData fields.

    Args:
        input_file: Path to input CSV file from log2timeline (l2tcsv format)
        output_file: Path to output enriched CSV file
        verbose: Print progress information
    """

    # Track all unique field names we encounter
    all_field_names = set()
    rows_data = []
    original_fieldnames = []

    # Column name mappings for Timesketch compatibility
    column_renames = {
        'date': 'datetime',
        'time': 'timestamp_desc',
        'desc': 'message'
    }

    print(f"[*] Reading input file: {input_file}")

    # First pass: read all data and collect field names
    with open(input_file, 'r', encoding='utf-8', newline='') as infile:
        reader = csv.DictReader(infile)
        original_fieldnames = list(reader.fieldnames)

        # Check for required columns
        if 'extra' not in original_fieldnames:
            print(f"[!] Error: Column 'extra' not found in CSV")
            print(f"[!] Available columns: {', '.join(original_fieldnames)}")
            print(f"[!] This script requires l2tcsv format from plaso/log2timeline")
            sys.exit(1)

        row_count = 0
        parsed_count = 0

        for row in reader:
            row_count += 1

            # Extract XML from extra field first
            extra_field = row.get('extra', '')
            xml_string = extract_xml_from_extra(extra_field)

            # Extract event ID - priority: XML > short field > extra field
            event_id = None
            if xml_string:
                event_id = extract_event_id_from_xml(xml_string)
            if not event_id:
                event_id = extract_event_id_from_short(row.get('short', ''))
            if not event_id:
                event_id = extract_event_id_from_extra(extra_field)

            parsed_fields = {}
            if xml_string and event_id:
                parsed_fields = parse_event_data(xml_string, event_id)
                if parsed_fields:
                    parsed_count += 1
                # Add the full xml_string as a separate field
                parsed_fields['xml_string'] = xml_string
                # Add event_id as a separate field
                parsed_fields['event_id'] = event_id

            # Track all field names
            all_field_names.update(parsed_fields.keys())

            # Store row data with parsed fields and apply column renames
            row_data = {}
            for key, value in row.items():
                # Rename columns according to mapping
                new_key = column_renames.get(key, key)
                row_data[new_key] = value

            # === Enrich datetime with timestamp_desc while keeping timestamp_desc column ===
            datetime_value = row_data.get('datetime', '')
            timestamp_desc_value = row_data.get('timestamp_desc', '')
            if datetime_value and timestamp_desc_value:
                # Avoid duplicating if timestamp_desc already appears in datetime
                if timestamp_desc_value not in datetime_value:
                    # Append time to date using a space separator
                    row_data['datetime'] = f"{datetime_value} {timestamp_desc_value}"

            # Add parsed fields
            row_data.update(parsed_fields)
            rows_data.append(row_data)

            if verbose and row_count % 1000 == 0:
                print(f"[*] Processed {row_count} rows, parsed {parsed_count} events...")

    print(f"[*] Processed {row_count} total rows")
    print(f"[*] Successfully parsed {parsed_count} events with EventData")
    print(f"[*] Found {len(all_field_names)} unique EventData fields")

    if verbose and all_field_names:
        sample_fields = sorted(all_field_names)[:10]
        print(f"[*] Sample fields: {', '.join(sample_fields)}")

    # Second pass: write enriched data
    print(f"[*] Writing enriched data to: {output_file}")

    # Apply column renames to original fieldnames
    renamed_fieldnames = [column_renames.get(col, col) for col in original_fieldnames]

    # Create final fieldnames: renamed originals + sorted parsed fields
    sorted_parsed_fields = sorted(all_field_names)
    final_fieldnames = renamed_fieldnames + sorted_parsed_fields

    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=final_fieldnames, extrasaction='ignore')
        writer.writeheader()

        for row_data in rows_data:
            # Ensure all fields exist (fill missing with empty string)
            for field in final_fieldnames:
                if field not in row_data:
                    row_data[field] = ''
            writer.writerow(row_data)

    print(f"[+] Successfully created enriched CSV: {output_file}")
    print(f"[+] Original columns: {len(renamed_fieldnames)}")
    print(f"[+] New parsed columns: {len(sorted_parsed_fields)}")
    print(f"[+] Total columns: {len(final_fieldnames)}")
    print(f"[+] Renamed columns: date→datetime, time→timestamp_desc, desc→message")


def main():
    parser = argparse.ArgumentParser(
        description='Parse EVTX EventData XML from log2timeline l2tcsv and create enriched Timesketch-compatible output',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python evtx_parser.py input.csv output.csv

  # Verbose mode
  python evtx_parser.py input.csv output.csv -v

Note: This script expects l2tcsv format from plaso/log2timeline with the 'extra' column
containing xml_string data.
        """
    )

    parser.add_argument('input_file', help='Input CSV file from log2timeline (l2tcsv format)')
    parser.add_argument('output_file', help='Output enriched CSV file')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print verbose progress information')

    args = parser.parse_args()

    # Validate input file exists
    if not Path(args.input_file).exists():
        print(f"[!] Error: Input file not found: {args.input_file}")
        sys.exit(1)

    # Process the CSV
    try:
        process_csv(args.input_file, args.output_file, args.verbose)
    except Exception as e:
        print(f"[!] Error processing file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
