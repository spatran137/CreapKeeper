#!/usr/bin/python

import sqlite3
import time
import tkinter as tk

#Insert into db 1 into the count feild and the date time of the event
def InsertCount():
    conn = sqlite3.connect('Counter.db')
    Date = time.ctime()
    Count = 1
    conn.execute('INSERT INTO tb_count (COUNT, DATE) VALUES (?, ?)',
                 (Count, Date))
    conn.commit()
    conn.close()

#Insert into db 1 into the creap feild and the date time of the evnet
def InsertCreap():
    conn = sqlite3.connect('Counter.db')
    Date = time.ctime()
    Creap = 1
    conn.execute('INSERT INTO tb_count (CREAP, DATE) VALUES (?, ?)',
                 (Creap, Date))
    conn.commit()
    conn.close()

#build teh buttons that are used to insert the count into the db
master = tk.Tk()
b = tk.Button(master, text ="Count", command = InsertCount)
b.pack()
b2 = tk.Button(master, text ="Creap", command = InsertCreap)
b2.pack()
#top.mainloop()

