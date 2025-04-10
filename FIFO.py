from queue import Queue
from datetime import datetime
from typing import List, NamedTuple, Tuple, Optional, Dict
from collections import deque, defaultdict
from pytz import timezone

class Transaction:
	def __init__(self,
			amount: float, price: float, costs: float, date: datetime):
		self.amount = amount # Total amounts of stock purchased.
		self.price = price # Price for one stock purchased.
		self.costs = costs # Other costs involved in the transaction.
		self.date = date # The time of the transaction.

	def __repr__(self) -> str:
		return f"Amount: {self.amount}, Price: {self.price}, " + \
			f"Costs: {self.costs}, Date: {self.date}"

	# Return true if the transaction is buying, false if selling.
	def is_buy(self) -> bool:
		assert self.amount != 0
		return self.amount > 0

	# Get the cost basis of the transaction, if the transaction is purchase,
	# also consider the buying price.
	def total_costs(self) -> float:
		ret = self.costs
		if self.is_buy():
			ret += self.amount * self.price
		return ret

	# Get the partial other costs of a selling.
	def partial_costs(self, amount: float) -> float:
		assert not self.is_buy() and amount <= -self.amount
		return self.costs * amount / -self.amount

	# Get the sales of the selling transaction.
	def sales(self, amount: Optional[float] = None) -> float:
		assert not self.is_buy()
		return -self.amount * self.price if amount is None \
			else amount * self.price

	# Sell part (`amount`) of the stock, return the cost basis of such partial
	# purchase. Also update `self.amount` and `self.costs` to the remaining.
	def sell_parts(self, amount: float) -> float:
		assert amount < self.amount
		part_costs = self.costs * amount / self.amount
		self.amount -= amount
		self.costs -= part_costs
		return part_costs + amount * self.price

	def split(self, multiplier: float) -> None:
		self.amount *= multiplier
		self.price /= multiplier

class Report:
	def __init__(self, amount: float, date_acquired: datetime, costs: float, \
		date_sold: datetime, sales: float):
		self.amount: float = amount
		self.date_acquired: datetime = date_acquired
		self.costs: float = costs
		self.date_sold: datetime = date_sold
		self.sales: float = sales

	def __repr__(self):
		return f"Amount: {self.amount}, Acquired: {self.date_acquired}, " + \
			f"Costs: {self.costs}, Sold: {self.date_sold}, Sales: {self.sales}"

	def profit(self) -> float:
		return self.sales - self.costs

	def is_single(self, other: "Report") -> bool:
		return self.date_acquired == other.date_acquired and \
			self.date_sold == other.date_sold

	def merge(self, other: "Report") -> None:
		assert self.is_single(other)
		self.amount += other.amount
		self.costs += other.costs
		self.sales += other.sales

	def to_nec_csv_row(self, desc: str) -> str:
		ret = desc
		ret += f" - {self.amount} shares,"
		ret += self.date_acquired.strftime("%m/%d/%Y")
		ret += ','
		ret += self.date_sold.strftime("%m/%d/%Y")
		ret += ','
		ret += str(self.sales)
		ret += ','
		ret += str(self.costs)
		ret += ','
		profit = self.profit()
		ret += ",%f" % profit if profit >= 0 else "%f," % -profit
		ret += '\n'
		return ret

def to_nec_csv(reports: List[Tuple[str, Report]], descs: Dict[str, str]) -> str:
	ret = """\"(a) Kind of property and description
(if necessary, attach statement of
descriptive details not shown below)\",\"(b) Date acquired
mm/dd/yyyy\",\"(c) Date sold
mm/dd/yyyy\",\"(d) Sales price\",\"(e) Cost or
other basis\",\"(f) LOSS
If (e) is more than (d),
subtract (d) from (e).\",\"(g) GAIN
If (d) is more than (e),
subtract (e) from (d).\"\n"""
	for code, report in reports:
		ret += report.to_nec_csv_row(descs[code])
	return ret

class FIFO:
	def __init__(self):
		self._last_date: datetime = datetime.strptime("0001-01-02", "%Y-%m-%d") \
			.astimezone(timezone("US/Eastern"))
		self._queue: deque[Transaction] = deque()
		self._reports: List[Report] = []

	def __repr__(self):
		ret = "Queue:\n"
		for t in self._queue:
			ret += repr(t)
			ret += '\n'
		if len(self._reports) > 0:
			ret = "Reports:\n"
			for r in self._reports:
				ret += repr(r)
				ret += '\n'
		return ret

	def add_transaction(self, trans: Transaction) -> None:
		assert self._last_date <= trans.date, \
				"Must add transactions in ascending order!"
		self._last_date = trans.date

		if trans.is_buy():
			self._queue.append(trans)
		else:
			# Obtain the amount being sold (positive number).
			amount = -trans.amount
			while amount > 0:
				first = self._queue[0] # FIFO, so get the first transaction.
				# If the selling transaction covers all amounts of the first,
				# we remove the first one, and add a report entry.
				if first.amount <= amount:
					self._queue.popleft()
					self._reports.append(Report(first.amount, first.date,
						trans.partial_costs(first.amount) + first.total_costs(),
						trans.date, trans.sales(first.amount)))
					amount -= first.amount
				# Only sell parts of the purchased stock in the `first`.
				else: # first.amount > amount
					self._reports.append(Report(amount, first.date,
						trans.partial_costs(amount) + first.sell_parts(amount),
						trans.date, trans.sales(amount)))
					amount = 0

	def get_reports(self, merge: bool = True) -> List[Report]:
		reports = self._reports
		self._reports = []
		if merge and len(reports) > 0:
			new_reports = []
			r = iter(reports)
			# Fetch the report entry for accumulation.
			acc = next(r)
			while True:
				try:
					report = next(r)
				except StopIteration:
					break
				# If the entry is the same trade as the accumulation report,
				# we merge them into the same report.
				if acc.is_single(report):
					acc.merge(report)
				# Otherwise, record the last accumulation report and set the
				# new one.
				else:
					new_reports.append(acc)
					acc = report
			# Also record the final accumulation report.
			new_reports.append(acc)
			return new_reports
		else:
			return reports

	def split(self, multiplier: float) -> None:
		for trans in self._queue:
			trans.split(multiplier)

class StockStatement:
	def __init__(self):
		self._all_stocks: defaultdict[str, FIFO] = defaultdict(lambda: FIFO())

	def __repr__(self):
		ret = ""
		for k, v in self._all_stocks.items():
			ret += k
			ret += ':\n'
			ret += repr(v)
		return ret

	def add_transaction(self, stock: str, trans: Transaction) -> None:
		assert type(stock) is str
		self._all_stocks[stock].add_transaction(trans)

	def get_reports(self) -> List[Tuple[str, Report]]:
		ret = []
		for k, v in self._all_stocks.items():
			ret.extend(map(lambda x: (k, x), v.get_reports()))
		return ret

	def split(self, code: str, multiplier: float) -> None:
		assert code in self._all_stocks
		self._all_stocks[code].split(multiplier)

