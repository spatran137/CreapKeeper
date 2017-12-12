#!/usr/bin/python

import sqlite3
import time
from time import sleep

#this was needed becase the recoreds were not getting inserted
sleep(0.1)

#Insert into db 1 into the creap feild and the date time of the evnet
def InsertCreap():
    conn = sqlite3.connect('Counter.db')
    Date = time.ctime()
    Creap = 1
    conn.execute('INSERT INTO tb_count (CREAP, DATE) VALUES (?, ?)',
                 (Creap, Date))
    conn.commit()
    conn.close()
    
#Call InsertCreap to add a 1 to the creap field
InsertCreap()

