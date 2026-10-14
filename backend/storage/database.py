import sqlite3
connection=sqlite3.connect(
    "mesh_network.db",
    check_same_thread=False
)
cursor=connection.cursor()
cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS packets (
        packet_id TEXT PRIMARY KEY,
        source_id TEXT,
        destination_id TEXT,
        payload TEXT,
        delivered INTEGER,
        route TEXT
    )
    '''
)
connection.commit()