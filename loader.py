from sshtunnel import SSHTunnelForwarder
import mysql.connector
import os
import subprocess
import json
import config

# ---------- local paths ---------- #
PCAP_DIR = "pcap"  # raw .pcap / .pcapng files
TEXT_DIR = "pcap_text"  # where tshark text dumps will be stored
TOPO_FILE = "topology/p4app_asym_flowlet.json"

# ---------- make sure pcap_text exists ---------- #
os.makedirs(TEXT_DIR, exist_ok=True)

# ---------- convert all pcap files to text once ---------- #
for fn in os.listdir(PCAP_DIR):
    if fn.endswith((".pcap", ".pcapng")):
        in_p = os.path.join(PCAP_DIR, fn)
        out_p = os.path.join(TEXT_DIR, fn + ".txt")
        if os.path.exists(out_p):
            continue  # already converted
        print(f"Converting {fn} → {out_p} …")
        subprocess.run(
            ["tshark", "-r", in_p], stdout=open(out_p, "w"), stderr=subprocess.DEVNULL
        )

# ---------- open SSH tunnel & DB ---------- #
with SSHTunnelForwarder(
    ("3.148.99.172", 22),
    ssh_username=config.ssh_username,
    ssh_private_key=config.ssh_private_key,
    remote_bind_address=config.remote_bind_address,
    local_bind_address=config.local_bind_address,
):

    conn = mysql.connector.connect(
        host=config.host, port=config.port, user=config.user, password=config.password
    )
    cur = conn.cursor(buffered=True)

    # ---------- DB / table setup (CREATE IF NOT EXISTS) ---------- #
    cur.execute("CREATE DATABASE IF NOT EXISTS network_traffic")
    cur.execute("USE network_traffic")

    cur.execute(
        """CREATE TABLE IF NOT EXISTS switches (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) UNIQUE,
        location VARCHAR(255))"""
    )

    cur.execute(
        """CREATE TABLE IF NOT EXISTS hosts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100) UNIQUE,
        ip_address VARCHAR(45),
        mac_address VARCHAR(50),
        location VARCHAR(255))"""
    )

    cur.execute(
        """CREATE TABLE IF NOT EXISTS ports (
        id INT AUTO_INCREMENT PRIMARY KEY,
        switch_id INT,
        port_number INT,
        description VARCHAR(255),
        UNIQUE (switch_id, port_number),
        FOREIGN KEY (switch_id) REFERENCES switches(id) ON DELETE CASCADE)"""
    )

    cur.execute(
        """CREATE TABLE IF NOT EXISTS links (
        id INT AUTO_INCREMENT PRIMARY KEY,
        port1_id INT,
        port2_id INT,
        link_type VARCHAR(50),
        bandwidth INT,
        FOREIGN KEY (port1_id) REFERENCES ports(id) ON DELETE CASCADE,
        FOREIGN KEY (port2_id) REFERENCES ports(id) ON DELETE CASCADE)"""
    )

    cur.execute(
        """CREATE TABLE IF NOT EXISTS packets (
        id INT AUTO_INCREMENT PRIMARY KEY,
        packet_number INT,
        timestamp_seconds DOUBLE,
        src_ip VARCHAR(45),
        dst_ip VARCHAR(45),
        protocol VARCHAR(10),
        total_length INT,
        tcp_flags VARCHAR(100),
        seq BIGINT,
        ack BIGINT,
        window_size INT,
        payload_length INT,
        mss INT,
        sack_perm BOOLEAN,
        tsval BIGINT,
        tsecr BIGINT,
        window_scale INT,
        capture_direction VARCHAR(10),
        src_port_id INT,
        dst_port_id INT,
        src_l4_port INT,
        dst_l4_port INT,
        FOREIGN KEY (src_port_id) REFERENCES ports(id),
        FOREIGN KEY (dst_port_id) REFERENCES ports(id))"""
    )

    topo = json.load(open(TOPO_FILE))
    sw_names = topo["topology"].get("switches", {})
    links = topo["topology"].get("links", [])

    for sw in sw_names:
        cur.execute("INSERT IGNORE INTO switches(name) VALUES (%s)", (sw,))
    conn.commit()

    cur.execute("SELECT id,name FROM switches")
    switch_id = {name: sid for sid, name in cur.fetchall()}
    port_counter = {sw: 1 for sw in sw_names}
    port_id_map = {}

    def ensure_port(sw: str):
        num = port_counter[sw]
        key = (sw, num)
        if key not in port_id_map:
            cur.execute(
                "INSERT IGNORE INTO ports(switch_id,port_number,description) VALUES(%s,%s,%s)",
                (switch_id[sw], num, "auto"),
            )
            conn.commit()
            cur.execute(
                "SELECT id FROM ports WHERE switch_id=%s AND port_number=%s",
                (switch_id[sw], num),
            )
            port_id_map[key] = cur.fetchone()[0]
            port_counter[sw] += 1
        return port_id_map[key]

    hosts = set()
    for n1, n2, *meta in links:
        bw = meta[0].get("bw") if meta else None
        if n1.startswith("h"):
            hosts.add(n1)
        if n2.startswith("h"):
            hosts.add(n2)

        if n1.startswith("s"):
            p1 = ensure_port(n1)
        if n2.startswith("s"):
            p2 = ensure_port(n2)
        if n1.startswith("s") and n2.startswith("s"):
            cur.execute(
                "INSERT IGNORE INTO links(port1_id,port2_id,link_type,bandwidth) VALUES(%s,%s,'switch-switch',%s)",
                (p1, p2, bw),
            )
        elif n1.startswith("h") and n2.startswith("s"):
            cur.execute(
                "INSERT IGNORE INTO links(port1_id,port2_id,link_type,bandwidth) VALUES(%s,%s,'host-switch',%s)",
                (p2, p2, bw),
            )
        elif n1.startswith("s") and n2.startswith("h"):
            cur.execute(
                "INSERT IGNORE INTO links(port1_id,port2_id,link_type,bandwidth) VALUES(%s,%s,'switch-host',%s)",
                (p1, p1, bw),
            )
    conn.commit()

    for h in hosts:
        mac = f"00:00:00:00:00:{int(h[1:]):02x}"
        cur.execute(
            "INSERT IGNORE INTO hosts(name,mac_address) VALUES(%s,%s)", (h, mac)
        )
    conn.commit()

    def port_id_from_filename(fname: str):
        sw, rest = fname.split("-", 1)
        iface = rest.split("_", 1)[0]
        idx = int(iface.replace("eth", ""))
        return port_id_map.get((sw, idx))

    for fn in os.listdir(TEXT_DIR):
        if not fn.endswith(".txt"):
            continue
        print(f"Inserting packets from {fn} …")
        direction = "in" if "_in" in fn else "out"
        port_id = port_id_from_filename(fn)
        if not port_id:
            print(f"  Skipping {fn}: unknown port")
            continue

        lines_inserted = 0
        with open(os.path.join(TEXT_DIR, fn)) as f:
            for ln, line in enumerate(f, 1):
                if ln % 1000 == 0:
                    print(f"   {fn}: {ln} lines processed…")
                parts = line.strip().split()
                if len(parts) < 10 or "→" not in parts:
                    continue
                try:
                    pkt_no = int(parts[0])
                    ts_sec = float(parts[1])
                    src_ip = parts[2]
                    dst_ip = parts[4]
                    proto = parts[5]
                    length = int(parts[6]) if parts[6].isdigit() else None
                except (ValueError, IndexError):
                    continue

                flags = ""
                seq = ack = win = plen = mss = tsv = tse = wsc = None
                sack = False

                for tok in parts:
                    if tok.startswith("["):
                        flags = tok
                    elif tok.startswith("Seq="):
                        seq = int(tok[4:])
                    elif tok.startswith("Ack="):
                        ack = int(tok[4:])
                    elif tok.startswith("Win="):
                        win = int(tok[4:])
                    elif tok.startswith("Len="):
                        plen = int(tok[4:])
                    elif tok.startswith("MSS="):
                        mss = int(tok[4:])
                    elif tok == "SACK_PERM":
                        sack = True
                    elif tok.startswith("TSval="):
                        tsv = int(tok[6:])
                    elif tok.startswith("TSecr="):
                        tse = int(tok[6:])
                    elif tok.startswith("WS="):
                        wsc = int(tok[3:])

                # extract L4 port numbers (e.g., 42763 → 35722)
                l4_src_port = l4_dst_port = None
                try:
                    arrows = [i for i, tok in enumerate(parts) if tok == "→"]
                    for idx in arrows:
                        ps = parts[idx - 1]
                        pd = parts[idx + 1]
                        if ps.isdigit() and pd.isdigit():
                            l4_src_port = int(ps)
                            l4_dst_port = int(pd)
                            break
                except Exception:
                    pass

                src_pid = port_id if direction == "out" else None
                dst_pid = port_id if direction == "in" else None

                cur.execute(
                    """INSERT INTO packets(
                        packet_number,timestamp_seconds,src_ip,dst_ip,protocol,total_length,
                        tcp_flags,seq,ack,window_size,payload_length,mss,sack_perm,tsval,tsecr,window_scale,
                        capture_direction,src_port_id,dst_port_id,src_l4_port,dst_l4_port)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        pkt_no,
                        ts_sec,
                        src_ip,
                        dst_ip,
                        proto,
                        length,
                        flags,
                        seq,
                        ack,
                        win,
                        plen,
                        mss,
                        sack,
                        tsv,
                        tse,
                        wsc,
                        direction,
                        src_pid,
                        dst_pid,
                        l4_src_port,
                        l4_dst_port,
                    ),
                )
                lines_inserted += 1
        conn.commit()
        print(f"   {fn}: committed {lines_inserted} rows.")

    cur.close()
    conn.close()
print("Done!")
