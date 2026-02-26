from django.db import connection
cursor = connection.cursor()
cursor.execute(chr(83)+chr(69)+chr(76)+chr(69)+chr(67)+chr(84)+chr(32)+chr(110)+chr(97)+chr(109)+chr(101)+chr(32)+chr(70)+chr(82)+chr(79)+chr(77)+chr(32)+chr(115)+chr(113)+chr(108)+chr(105)+chr(116)+chr(101)+chr(95)+chr(109)+chr(97)+chr(115)+chr(116)+chr(101)+chr(114)+chr(32)+chr(87)+chr(72)+chr(69)+chr(82)+chr(69)+chr(32)+chr(116)+chr(121)+chr(112)+chr(101)+chr(61)+chr(39)+chr(116)+chr(97)+chr(98)+chr(108)+chr(101)+chr(39)+chr(32)+chr(79)+chr(82)+chr(68)+chr(69)+chr(82)+chr(32)+chr(66)+chr(89)+chr(32)+chr(110)+chr(97)+chr(109)+chr(101))
tables = cursor.fetchall()
for (table,) in tables:
    cursor.execute(f"SELECT COUNT(*) FROM \"{table}\"")
    count = cursor.fetchone()[0]
    print(f"{table}: {count} registros")
