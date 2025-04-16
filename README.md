# NEC "Capital Gains and Losses" Table Generator

Since SprinTax does not support manually uploading trade records without 1099, this script aims to serve this purpose and automatically generates the "Capital Gains and Losses" in the "Schedule NEC", in the form of CSV file that can be filed as an attachment (because the spaces in the Schedule NEC is too small).

## Usage of FIFO

```python
stmt = StockStatement()

# Each transaction should be added in ascending time order.
# add_transaction(self, stock: str, trans: Transaction)
# `stock`: code of the stock, only serves an identifier (e.g., "NVDL").
# `trans`: Transaction instance describing the transaction.
stmt.add_transaction(stock, trans)

# When stock split happens during `add_transaction`, this should be called
# when the time of split is reached. The multiplier is how many shares will
# be split from one share.
stmt.split(stock, multiplier)

# Obtain the reports for the year, converting to CSV file.
# `descs` is a dictionary mapping stock code to its detailed descriptions.
to_nec_csv(stmt.get_reports(), descs)

# `Tiger.py` shows an example of how to use it to generate the table for
# trading records of Tiger Brokerage.
```