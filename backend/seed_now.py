from db import init_db, get_connection

init_db()
con = get_connection()
count = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
deploys = con.execute("SELECT COUNT(*) FROM system_deployments").fetchone()[0]
incidents = con.execute("SELECT COUNT(*) FROM gateway_incidents").fetchone()[0]
print(f"transactions={count}")
print(f"deployments={deploys}")
print(f"incidents={incidents}")
