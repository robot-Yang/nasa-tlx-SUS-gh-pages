#!/usr/bin/env python3
"""
Export participant payment list to an Excel (.xlsx) file.

Columns:
- First Name
- Last Name
- Camipro Number
- Amount (CHF)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import os
import re
import zipfile
from xml.sax.saxutils import escape


DEFAULT_AMOUNT_CHF = 25


def latest_csv_in_downloads() -> str:
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    candidates = sorted(glob.glob(os.path.join(downloads_dir, "*.csv")), key=os.path.getmtime, reverse=True)
    return candidates[0] if candidates else ""


def parse_name_and_camipro(raw_participant: str):
    text = (raw_participant or "").strip()
    if not text:
        return "", "", ""

    # Expected format from exporter: "name (123456)".
    m = re.match(r"^(.*?)\s*\((.*?)\)\s*$", text)
    if m:
        name_text = m.group(1).strip()
        camipro = m.group(2).strip()
    else:
        name_text = text
        camipro = ""

    parts = [p for p in name_text.split() if p]
    if len(parts) >= 2:
        first_name = parts[0]
        last_name = " ".join(parts[1:])
    elif len(parts) == 1:
        first_name = parts[0]
        last_name = ""
    else:
        first_name = ""
        last_name = ""
    return first_name, last_name, camipro


def collect_participants(csv_path: str, amount_chf: int):
    rows = []
    seen = set()
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_participant = (row.get("Participant") or "").strip()
            if not raw_participant:
                continue
            first_name, last_name, camipro = parse_name_and_camipro(raw_participant)
            dedupe_key = (first_name, last_name, camipro)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rows.append([first_name, last_name, camipro, str(amount_chf)])
    return rows


def col_name(index: int) -> str:
    s = ""
    n = index + 1
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def worksheet_xml(headers, data_rows):
    rows_xml = []

    def make_row(ridx, values):
        cells = []
        for cidx, value in enumerate(values):
            ref = f"{col_name(cidx)}{ridx}"
            txt = escape(str(value))
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{txt}</t></is></c>')
        return f'<row r="{ridx}">{"".join(cells)}</row>'

    rows_xml.append(make_row(1, headers))
    for i, row_values in enumerate(data_rows, start=2):
        rows_xml.append(make_row(i, row_values))

    dimension = f"A1:{col_name(max(len(headers) - 1, 0))}{max(1, len(data_rows) + 1)}"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/>'
        "<sheetViews><sheetView workbookViewId=\"0\"/></sheetViews>"
        "<sheetFormatPr defaultRowHeight=\"15\"/>"
        f"<sheetData>{''.join(rows_xml)}</sheetData>"
        "</worksheet>"
    )


def write_xlsx(output_path: str, headers, data_rows):
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>
"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Participants" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>
"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf/></cellStyleXfs>
  <cellXfs count="1"><xf xfId="0"/></cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>
"""
    sheet1 = worksheet_xml(headers, data_rows)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/styles.xml", styles)
        zf.writestr("xl/worksheets/sheet1.xml", sheet1)


def parse_args():
    parser = argparse.ArgumentParser(description="Export participant credit list to .xlsx")
    parser.add_argument("csv_path", nargs="?", default="", help="Input CSV path (default: latest CSV in ~/Downloads)")
    parser.add_argument("--out", default="", help="Output .xlsx path")
    parser.add_argument("--amount", type=int, default=DEFAULT_AMOUNT_CHF, help="Credit amount in CHF (default: 25)")
    return parser.parse_args()


def main():
    args = parse_args()
    csv_path = args.csv_path or latest_csv_in_downloads()
    if not csv_path:
        raise SystemExit("No CSV file found. Provide one explicitly.")
    if not os.path.isfile(csv_path):
        raise SystemExit(f"CSV not found: {csv_path}")

    rows = collect_participants(csv_path, amount_chf=args.amount)
    if not rows:
        raise SystemExit("No participants found in CSV.")

    if args.out:
        out_path = args.out
    else:
        stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = os.path.join(os.getcwd(), f"participants_credit_{stamp}.xlsx")

    headers = ["First Name", "Last Name", "Camipro Number", "Amount (CHF)"]
    write_xlsx(out_path, headers, rows)
    print(f"Input CSV: {csv_path}")
    print(f"Participants exported: {len(rows)}")
    print(f"Output Excel: {out_path}")


if __name__ == "__main__":
    main()

