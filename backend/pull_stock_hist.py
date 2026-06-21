"""批量拉取全A股历史K线到 stock_hist"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import baostock as bs
from datetime import date, timedelta
from services.storage import get_conn, put_conn

DAYS = 120

bs.login()
end_date = date.today().strftime("%Y-%m-%d")
start_date = (date.today() - timedelta(days=DAYS)).strftime("%Y-%m-%d")

# 全A股列表
rs = bs.query_stock_basic()
stocks = []
while (rs.error_code == '0') & rs.next():
    row = rs.get_row_data()
    code, name = row[0], row[1]
    if row[4] == '1' and not code.endswith(('.000001','.000002','.000003','.399001','.399005','.399006')):
        stocks.append((code, name))

print(f"共 {len(stocks)} 只A股，拉取近{DAYS}天日K...")

conn = get_conn()
batch = []
total = 0

SQL = """
    INSERT INTO stock_hist (code, trade_date, open, close, high, low, volume, amount, change_pct)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (code, trade_date) DO UPDATE SET
        open=EXCLUDED.open, close=EXCLUDED.close, high=EXCLUDED.high, low=EXCLUDED.low,
        volume=EXCLUDED.volume, amount=EXCLUDED.amount, change_pct=EXCLUDED.change_pct
"""

for i, (code, name) in enumerate(stocks):
    rs = bs.query_history_k_data_plus(code, "date,open,high,low,close,volume,amount,pctChg",
                                       start_date=start_date, end_date=end_date,
                                       frequency='d', adjustflag='2')
    while (rs.error_code == '0') & rs.next():
        rd = rs.get_row_data()
        batch.append((
            code, rd[0],
            float(rd[1]) if rd[1] and rd[1] != '' else None,
            float(rd[4]) if rd[4] and rd[4] != '' else None,
            float(rd[2]) if rd[2] and rd[2] != '' else None,
            float(rd[3]) if rd[3] and rd[3] != '' else None,
            float(rd[5]) if rd[5] and rd[5] != '' else None,
            float(rd[6]) if rd[6] and rd[6] != '' else None,
            float(rd[7]) if rd[7] and rd[7] != '' else None,
        ))

    # 每100只写一次库
    if len(batch) >= 5000:
        with conn.cursor() as cur:
            cur.executemany(SQL, batch)
        conn.commit()
        total += len(batch)
        print(f"  [{i+1}/{len(stocks)}] {code} {name} — 累计写入{total}条")
        batch = []

    if (i + 1) % 200 == 0:
        print(f"  [{i+1}/{len(stocks)}] {code} {name}")

# 最后一批
if batch:
    with conn.cursor() as cur:
        cur.executemany(SQL, batch)
    conn.commit()
    total += len(batch)

put_conn(conn)
bs.logout()
print(f"\n✅ 总计写入 {total} 条日K数据")
