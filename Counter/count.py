#!/usr/bin/python

import sqlite3
import time
from time import sleep

#this was needed because the records were not getting inserted
sleep(0.1)


#Insert into db 1 into the count feild and the date time of the event
def InsertCount():
    conn = sqlite3.connect('Counter.db')
    Date = time.ctime()
    Count = 1
    conn.execute('INSERT INTO tb_count (COUNT, DATE) VALUES (?, ?)',
                 (Count, Date))
    conn.commit()
    conn.close()

#Call InsertCount to add a 1 to the count field
InsertCount()

