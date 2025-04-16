import argparse
from datetime import datetime
from pytz import timezone
from FIFO import StockStatement, Transaction, Report, to_nec_csv
import csv
import os
import json
from typing import List, Dict, Tuple

def parse_float(f: str) -> float:
	return 0 if len(f) == 0 else float(f)

def proc_trade_header_row(row: List[str]) -> Dict[str, int]:
	ret = dict()
	for i in range(0, len(row)):
		if len(row[i]) > 0:
			ret[row[i]] = i
	return ret

def parse_trans(row: List[str], ti: Dict[str, int]) -> Transaction:
	costs = 0
	for i in range(ti["Amount"] + 1, ti["Realized P/L"]):
		costs += parse_float(row[i])
	costs = -costs
	time = row[ti["Trade Time"]]
	if "GMT+8" in time:
		time = time.replace("GMT+8", "+0800")
		time = datetime.strptime(time, "%Y-%m-%d\n%H:%M:%S, %z") \
			.astimezone(timezone("US/Eastern"))
	else:
		time = datetime.strptime(time, "%Y-%m-%d\n%H:%M:%S, US/Eastern") \
			.astimezone(timezone("US/Eastern"))
	return Transaction(float(row[ti["Quantity"]]),
		float(row[ti["Trade Price"]]), costs, time)

def process_csv(csv_path: str, stmt: StockStatement, splits: Dict[str, List]) \
	-> List[Tuple[str, Report]]:
	with open(csv_path, 'r', newline='') as fd:
		trades = csv.reader(fd)
		it_trades = iter(trades)
		while True:
			th = next(it_trades)
			if th[0] == "Trades" and th[1] == "" and th[2] == "" and th[3] == "":
				ti = proc_trade_header_row(th)
				break
		# `ti`: Convert header to index.
		# `th`: Convert index to header.

		all_transactions = []
		while True:
			try:
				row = next(it_trades)
			except StopIteration:
				break
			# May encounter different column format.
			if row[0] == "Trades" and \
				row[1] == "" and row[2] == "" and row[3] == "":
				ti = proc_trade_header_row(row)
				th = row
				continue
			# Only process Trades and DATA row. Also we only process non-summary
			# row, whose code is stored in the last summary row.
			if row[0] != "Trades" or row[3] != "DATA":
				continue
			if len(row[ti["Symbol"]]) > 0:
				cur_code = row[ti["Symbol"]]
			else:
				all_transactions.append(
					(parse_trans(row, ti), cur_code, len(all_transactions)))
		# If date is same, prioritize the row appearing first.
		all_transactions.sort(key=lambda k: (k[0].date, k[2]))

		for trans, code, _ in all_transactions:
			date = str(trans.date)
			if date in splits:
				stmt.split(splits[date][0], splits[date][1])
				del splits[date]
			stmt.add_transaction(code, trans)

		return stmt.get_reports()

def parse_descs(csv_files: List[str]) -> Dict[str, str]:
	ret = dict()
	for csv_file in csv_files:
		with open(csv_file, 'r') as fd:
			statement = csv.reader(fd)
			for row in statement:
				if row[0] == "Financial Instrument Information" and \
					row[3] == "DATA":
					ret[row[4]] = "%s (%s)" % (row[4], row[6])
	return ret

if __name__ == "__main__":
	args = argparse.ArgumentParser()
	args.add_argument("csv", nargs="+",
		help="CSV files of several continuous year. " + \
		"Each CSV file must contain all trades in a whole year.")
	args.add_argument("-s", "--splits",
		help="JSON file mapping date strings '20XX-XX-XX XX:XX:XX-04:00' " + \
		"to tuples [stock code, split multiplier].")
	args = args.parse_args()
	descs = parse_descs(args.csv)
	stmt = StockStatement()

	# Parse JSON file of stock splits.
	if args.splits is not None:
		with open(args.splits, 'r') as fd:
			splits = json.load(fd)
	else:
		splits = dict()

	for c in args.csv:
		print("Processing:", c)
		total_sales, total_costs, total_loss, total_gain = 0, 0, 0, 0
		reports = process_csv(c, stmt, splits)
		output_path = c[:-4] + ".nec.csv"
		with open(output_path, 'w') as fd:
			print("Storing results to:", output_path)
			fd.write(to_nec_csv(reports, descs))
		for code, report in reports:
			total_sales += report.sales
			total_costs += report.costs
			profit = report.profit()
			if profit >= 0:
				total_gain += profit
			else:
				total_loss += -profit
		print("Total Costs:", total_costs)
		print("Total Sales:", total_sales)
		print("Total Loss:", total_loss)
		print("Total Gain:", total_gain)
		print("Total Profit:", total_gain - total_loss)