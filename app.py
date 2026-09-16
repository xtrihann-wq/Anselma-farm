import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import datetime, date
import io

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Anselma Farm - PuyuhKu", layout="wide", page_icon="🐣")

# ==========================================
# 2. KONEKSI CLOUD DATABASE NEON
# ==========================================
conn = st.connection("postgresql", type="sql")

def init_db():
    with conn.session as s:
        s.execute(text('''CREATE TABLE IF NOT EXISTS produksi 
                     (id SERIAL PRIMARY KEY, Tanggal TEXT, Populasi_Aktif INTEGER, Mortalitas INTEGER, 
                      Telur_Butir INTEGER, Telur_Kg REAL, Pakan_Kg REAL)'''))
        
        s.execute(text('''CREATE TABLE IF NOT EXISTS kasir 
                     (id SERIAL PRIMARY KEY, Tanggal TEXT, Varian TEXT, Harga_Satuan INTEGER, 
                      Kuantitas INTEGER, Total_Rp INTEGER)'''))
                     
        s.execute(text('''CREATE TABLE IF NOT EXISTS pengeluaran 
                     (id SERIAL PRIMARY KEY, Tanggal TEXT, Kategori TEXT, Deskripsi TEXT, Nominal_Rp INTEGER)'''))
        s.commit()
        
    # Migrasi Pintar (Menambah kolom baru otomatis jika belum ada)
    try:
        with conn.session as s:
            s.execute(text("ALTER TABLE kasir ADD COLUMN Keterangan_Pelanggan TEXT;"))
            s.commit()
    except Exception: pass 
    
    try:
        with conn.session as s:
            s.execute(text("ALTER TABLE pengeluaran ADD COLUMN Jumlah_Karung REAL DEFAULT 0;"))
            s.commit()
    except Exception: pass

init_db()

def get_data(table_name):
    return conn.query(f"SELECT * FROM {table_name} ORDER BY Tanggal DESC, id DESC", ttl=0)

VARIAN_TELUR = {
    "Per Kilo (1 kg)": 32000,
    "Tengahan (0.5 kg)": 16000,
    "Seperempat (0.25 kg)": 8000,
    "Harga Khusus/Lainnya": 0
}

# ==========================================
# 3. MENGAMBIL DATA GLOBAL & HITUNG STOK/KAS
# ==========================================
df_prod = get_data('produksi')
df_kasir = get_data('kasir')
df_peng = get_data('pengeluaran')

# --- Kalkulasi Keuangan ---
total_masuk = df_kasir["total_rp"].sum() if not df_kasir.empty else 0
total_keluar = df_peng["nominal_rp"].sum() if not df_peng.empty else 0
sisa_kas = total_masuk - total_keluar

# --- Kalkulasi Stok Telur ---
total_telur_panen = df_prod["telur_kg"].sum() if not df_prod.empty else 0

def hitung_berat_terjual(row):
    var = str(row['varian'])
    qty = float(row['kuantitas'])
    if "1 kg" in var: return 1.0 * qty
    elif "0.5 kg" in var: return 0.5 * qty
    elif "0.25 kg" in var: return 0.25 * qty
    else: return 0.0 # Jika varian lainnya

if not df_kasir.empty:
    df_kasir['berat_terjual_kg'] = df_kasir.apply(hitung_berat_terjual, axis=1)
    total_telur_terjual = df_kasir['berat_terjual_kg'].sum()
else:
    total_telur_terjual = 0

sisa_telur_kg = total_telur_panen - total_telur_terjual

# --- Kalkulasi Stok Pakan ---
if not df_peng.empty and 'jumlah_karung' in df_peng.columns:
    total_karung_masuk = df_peng["jumlah_karung"].sum()
else:
    total_karung_masuk = 0
    
total_pakan_masuk_kg = total_karung_masuk * 50 # 1 Karung = 50 Kg
total_pakan_terpakai_kg = df_prod["pakan_kg"].sum() if not df_prod.empty else 0

sisa_pakan_kg = total_pakan_masuk_kg - total_pakan_terpakai_kg
sisa_pakan_karung = sisa_pakan_kg / 50 if sisa_pakan_kg > 0 else 0

# ==========================================
# 4. NAVIGASI & TAMPILAN SIDEBAR
# ==========================================
try:
    st.sidebar.image("logo.jpeg", use_container_width=True)
except: pass

st.sidebar.title("Anselma Farm")
st.sidebar.markdown("Sistem Manajemen Tersimpan")

# TAMPILAN SISA KAS
if sisa_kas >= 0:
    st.sidebar.success(f"💰 **Sisa Uang Kas:**\n### Rp {sisa_kas:,.0f}")
else:
    st.sidebar.error(f"⚠️ **Kas Minus:**\n### Rp {sisa_kas:,.0f}")

# TAMPILAN SISA STOK
st.sidebar.info(f"🥚 **Sisa Stok Telur:**\n### {sisa_telur_kg:.2f} Kg")

if sisa_pakan_kg >= 0:
    st.sidebar.warning(f"🌾 **Sisa Stok Pakan:**\n### {sisa_pakan_karung:.1f} Karung \n*({sisa_pakan_kg:.1f} Kg)*")
else:
    # Jika pakan minus (artinya peternak mencatat pakan harian tapi belum mencatat nota beli pakan)
    st.sidebar.error(f"🌾 **Sisa Pakan Minus!**\n### {sisa_pakan_kg:.1f} Kg\n*(Catat nota beli pakan di menu Pengeluaran)*")

st.sidebar.divider()
menu = st.sidebar.radio("Menu Navigasi:", [
    "📊 Dashboard Utama", 
    "📝 Catat Produksi Harian", 
    "🛒 Kasir / Penjualan", 
    "💸 Pencatatan Pengeluaran", 
    "📁 Export Excel (Rapi)",
    "✏️ Edit / Hapus Data"
])

# ==========================================
# 5. LOGIKA HALAMAN & UI
# ==========================================

# --- HALAMAN DASHBOARD ---
if menu == "📊 Dashboard Utama":
    st.title("📊 Dashboard Utama Anselma Farm")
    
    total_telur_kg = total_telur_panen
    total_pakan_kg = total_pakan_terpakai_kg
    fcr = (total_pakan_kg / total_telur_kg) if total_telur_kg > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Panen Telur", f"{total_telur_kg:.2f} Kg")
    with col2: st.metric("Rasio Pakan (FCR)", f"{fcr:.2f}")
    with col3: st.metric("Total Pemasukan", f"Rp {total_masuk:,.0f}")
    with col4: st.metric("Total Pengeluaran", f"Rp {total_keluar:,.0f}")

    st.divider()
    
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("📈 Tren Produksi Telur (Kg)")
        if not df_prod.empty:
            df_chart = df_prod.sort_values("tanggal")
            chart_prod = df_chart.groupby("tanggal")["telur_kg"].sum()
            st.line_chart(chart_prod, color="#F1C40F") 
        else:
            st.info("Belum ada data produksi.")
            
    with col_chart2:
        st.subheader("💰 Distribusi Pengeluaran")
        if not df_peng.empty:
            peng_kategori = df_peng.groupby('kategori')['nominal_rp'].sum()
            st.bar_chart(peng_kategori, color="#9B59B6") 
        else:
            st.info("Belum ada data pengeluaran.")

# --- HALAMAN PRODUKSI ---
elif menu == "📝 Catat Produksi Harian":
    st.title("📝 Pencatatan Produksi Harian")
    
    with st.form("form_produksi", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tgl = st.date_input("Tanggal Produksi", date.today())
            populasi = st.number_input("Populasi Aktif (Ekor)", min_value=0, value=1000)
            mati = st.number_input("Mortalitas / Afkir (Ekor)", min_value=0, value=0)
        with col2:
            telur_butir = st.number_input("Telur Dipanen (Butir)", min_value=0)
            telur_kg = st.number_input("Berat Telur (Kg)", min_value=0.0, format="%.2f")
            pakan = st.number_input("Konsumsi Pakan Hari Ini (Kg)", min_value=0.0, format="%.2f")
            
        if st.form_submit_button("Simpan Data"):
            pop_aktif = populasi - mati
            with conn.session as s:
                s.execute(text("INSERT INTO produksi (Tanggal, Populasi_Aktif, Mortalitas, Telur_Butir, Telur_Kg, Pakan_Kg) VALUES (:t, :pa, :m, :tb, :tk, :pk)"), 
                          {"t": str(tgl), "pa": pop_aktif, "m": mati, "tb": telur_butir, "tk": telur_kg, "pk": pakan})
                s.commit()
            st.success("✅ Data produksi tersimpan! Stok telur bertambah & stok pakan berkurang.")
            st.rerun()
            
    st.subheader("Riwayat Produksi Terbaru")
    st.dataframe(df_prod.head(5), use_container_width=True)

# --- HALAMAN KASIR ---
elif menu == "🛒 Kasir / Penjualan":
    st.title("🛒 Kasir Penjualan")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Input Transaksi Baru")
        tgl_kasir = st.date_input("Tanggal Transaksi", date.today())
        keterangan = st.text_input("Nama/Keterangan Pelanggan (Opsional)")
        varian = st.selectbox("Pilih Varian Berat", list(VARIAN_TELUR.keys()))
        harga_dasar = VARIAN_TELUR[varian]
        harga_satuan = st.number_input("Harga Satuan (Rp) - Bisa diedit", min_value=0, value=harga_dasar, step=500)
        kuantitas = st.number_input("Kuantitas (Jumlah)", min_value=1, value=1)
        
        total_harga = harga_satuan * kuantitas
        st.info(f"💵 **TOTAL PEMBAYARAN: Rp {total_harga:,.0f}**")
        
        if st.button("Simpan Transaksi 💾", use_container_width=True, type="primary"):
            with conn.session as s:
                s.execute(text("INSERT INTO kasir (Tanggal, Varian, Harga_Satuan, Kuantitas, Total_Rp, Keterangan_Pelanggan) VALUES (:t, :v, :hs, :k, :tot, :ket)"), 
                          {"t": str(tgl_kasir), "v": varian, "hs": harga_satuan, "k": kuantitas, "tot": total_harga, "ket": keterangan})
                s.commit()
            st.success(f"✅ Transaksi sukses! Sisa stok telur otomatis berkurang.")
            st.rerun()
                
    with col2:
        st.subheader("Riwayat Penjualan Terbaru")
        st.dataframe(df_kasir.head(5), use_container_width=True)

# --- HALAMAN PENGELUARAN (UPGRADED) ---
elif menu == "💸 Pencatatan Pengeluaran":
    st.title("💸 Catat Arus Kas Keluar")
    with st.form("form_pengeluaran", clear_on_submit=True):
        tgl_peng = st.date_input("Tanggal", date.today())
        kategori = st.selectbox("Kategori", ["Beli Pakan", "Vitamin/Obat", "Gaji Karyawan", "Listrik & Air", "Lainnya"])
        
        # Opsi khusus jika memilih "Beli Pakan"
        if kategori == "Beli Pakan":
            st.info("💡 Karena memilih 'Beli Pakan', silakan isi jumlah karung di bawah ini agar stok ter-update.")
            jml_karung = st.number_input("Jumlah Beli (Karung) - 1 Karung=50kg", min_value=0.0, step=0.5)
        else:
            jml_karung = 0.0
            
        deskripsi = st.text_input("Keterangan Detail (Contoh: Beli sentrat)")
        nominal = st.number_input("Nominal (Rp)", min_value=0, step=10000)
        
        if st.form_submit_button("Simpan Pengeluaran"):
            with conn.session as s:
                s.execute(text("INSERT INTO pengeluaran (Tanggal, Kategori, Deskripsi, Nominal_Rp, Jumlah_Karung) VALUES (:t, :k, :d, :n, :jk)"), 
                          {"t": str(tgl_peng), "k": kategori, "d": deskripsi, "n": nominal, "jk": jml_karung})
                s.commit()
            st.success("✅ Pengeluaran tercatat! Kas berkurang dan Stok Pakan otomatis bertambah.")
            st.rerun()
            
    st.subheader("Riwayat Pengeluaran Terbaru")
    st.dataframe(df_peng.head(5), use_container_width=True)

# --- HALAMAN EXPORT EXCEL ---
elif menu == "📁 Export Excel (Rapi)":
    st.title("📁 Export Data ke Excel")
    
    if st.button("🔄 Generate File Excel"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook  = writer.book
            format_rp = workbook.add_format({'num_format': 'Rp #,##0'})
            format_kg = workbook.add_format({'num_format': '0.00'})
            
            def create_neat_sheet(df, sheet_name):
                if df.empty:
                    df = pd.DataFrame({"Keterangan": ["Belum ada data"]})
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                worksheet = writer.sheets[sheet_name]
                max_row, max_col = df.shape
                column_settings = [{'header': column} for column in df.columns]
                worksheet.add_table(0, 0, max_row, max_col - 1, {'columns': column_settings, 'style': 'Table Style Medium 9'})
                
                for i, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 4
                    if 'rp' in col.lower() or 'harga' in col.lower():
                        worksheet.set_column(i, i, max_len, format_rp)
                    elif 'kg' in col.lower():
                        worksheet.set_column(i, i, max_len, format_kg)
                    else:
                        worksheet.set_column(i, i, max_len)

            create_neat_sheet(df_prod, 'Data_Produksi')
            create_neat_sheet(df_kasir, 'Data_Penjualan')
            create_neat_sheet(df_peng, 'Data_Pengeluaran')
            
        output.seek(0)
        st.success("✅ File berhasil dibuat!")
        st.download_button(label="📥 Download Excel (.xlsx)", data=output,
                           file_name=f"Laporan_AnselmaFarm_{datetime.today().strftime('%d_%m_%Y')}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- HALAMAN EDIT / HAPUS DATA ---
elif menu == "✏️ Edit / Hapus Data":
    st.title("✏️ Edit atau Hapus Pencatatan")
    st.markdown("Pilih tabel dan ID data yang ingin diperbaiki.")
    
    tabel_pilihan = st.selectbox("Pilih Kategori Pencatatan:", ["produksi", "kasir", "pengeluaran"])
    
    if tabel_pilihan == "produksi": df_edit = df_prod
    elif tabel_pilihan == "kasir": df_edit = df_kasir
    else: df_edit = df_peng
    
    if df_edit.empty:
        st.info(f"Belum ada data pada kategori {tabel_pilihan}.")
    else:
        st.dataframe(df_edit, use_container_width=True)
        st.divider()
        st.subheader("Pengaturan Data Spesifik")
        
        aksi = st.radio("Pilih Tindakan:", ["✏️ Edit Data", "🗑️ Hapus Data"], horizontal=True)
        id_pilih = st.selectbox("Pilih ID Data (Kolom 'id'):", df_edit["id"].tolist())
        row_data = df_edit[df_edit["id"] == id_pilih].iloc[0]
        
        if aksi == "✏️ Edit Data":
            with st.form("form_edit_data"):
                st.info(f"Sedang mengedit ID: **{id_pilih}**")
                
                if tabel_pilihan == "produksi":
                    tgl_e = st.date_input("Tanggal", datetime.strptime(row_data["tanggal"], "%Y-%m-%d").date())
                    pop_e = st.number_input("Populasi Aktif", value=int(row_data["populasi_aktif"]))
                    mati_e = st.number_input("Mortalitas", value=int(row_data["mortalitas"]))
                    butir_e = st.number_input("Telur (Butir)", value=int(row_data["telur_butir"]))
                    kg_e = st.number_input("Berat Telur (Kg)", value=float(row_data["telur_kg"]), format="%.2f")
                    pakan_e = st.number_input("Pakan (Kg)", value=float(row_data["pakan_kg"]), format="%.2f")
                    
                    if st.form_submit_button("Update Data"):
                        with conn.session as s:
                            s.execute(text("UPDATE produksi SET Tanggal=:t, Populasi_Aktif=:pa, Mortalitas=:m, Telur_Butir=:tb, Telur_Kg=:tk, Pakan_Kg=:pk WHERE id=:id"),
                                      {"t": str(tgl_e), "pa": pop_e, "m": mati_e, "tb": butir_e, "tk": kg_e, "pk": pakan_e, "id": int(id_pilih)})
                            s.commit()
                        st.success("✅ Diperbarui! Stok telur & pakan otomatis terkoreksi.")
                        st.rerun()

                elif tabel_pilihan == "kasir":
                    tgl_e = st.date_input("Tanggal", datetime.strptime(row_data["tanggal"], "%Y-%m-%d").date())
                    ket_lama = row_data["keterangan_pelanggan"] if "keterangan_pelanggan" in row_data and pd.notna(row_data["keterangan_pelanggan"]) else ""
                    ket_e = st.text_input("Keterangan", value=str(ket_lama))
                    varian_e = st.text_input("Varian", value=str(row_data["varian"]))
                    harga_e = st.number_input("Harga Satuan", value=int(row_data["harga_satuan"]))
                    qty_e = st.number_input("Kuantitas", value=int(row_data["kuantitas"]))
                    tot_e = harga_e * qty_e
                    st.write(f"**Total Baru: Rp {tot_e:,.0f}**")
                    
                    if st.form_submit_button("Update Data"):
                        with conn.session as s:
                            s.execute(text("UPDATE kasir SET Tanggal=:t, Varian=:v, Harga_Satuan=:hs, Kuantitas=:k, Total_Rp=:tot, Keterangan_Pelanggan=:ket WHERE id=:id"),
                                      {"t": str(tgl_e), "v": varian_e, "hs": harga_e, "k": qty_e, "tot": tot_e, "ket": ket_e, "id": int(id_pilih)})
                            s.commit()
                        st.success("✅ Diperbarui! Sisa stok telur laku otomatis terkoreksi.")
                        st.rerun()

                elif tabel_pilihan == "pengeluaran":
                    tgl_e = st.date_input("Tanggal", datetime.strptime(row_data["tanggal"], "%Y-%m-%d").date())
                    kategori_e = st.text_input("Kategori", value=str(row_data["kategori"]))
                    
                    jml_karung_lama = float(row_data["jumlah_karung"]) if "jumlah_karung" in row_data and pd.notna(row_data["jumlah_karung"]) else 0.0
                    if kategori_e == "Beli Pakan":
                        jml_karung_e = st.number_input("Jumlah Karung Pakan", value=jml_karung_lama, step=0.5)
                    else:
                        jml_karung_e = 0.0
                        
                    deskripsi_e = st.text_input("Deskripsi", value=str(row_data["deskripsi"]))
                    nominal_e = st.number_input("Nominal (Rp)", value=int(row_data["nominal_rp"]))
                    
                    if st.form_submit_button("Update Data"):
                        with conn.session as s:
                            s.execute(text("UPDATE pengeluaran SET Tanggal=:t, Kategori=:k, Deskripsi=:d, Nominal_Rp=:n, Jumlah_Karung=:jk WHERE id=:id"),
                                      {"t": str(tgl_e), "k": kategori_e, "d": deskripsi_e, "n": nominal_e, "jk": jml_karung_e, "id": int(id_pilih)})
                            s.commit()
                        st.success("✅ Diperbarui! Stok pakan otomatis terkoreksi.")
                        st.rerun()
                        
        else:
            with st.form("form_hapus_data"):
                st.error(f"Anda akan menghapus data ID: **{id_pilih}**")
                konfirmasi = st.checkbox("Ya, saya yakin.")
                if st.form_submit_button("🚨 Hapus Data"):
                    if konfirmasi:
                        with conn.session as s:
                            s.execute(text(f"DELETE FROM {tabel_pilihan} WHERE id = :id"), {"id": int(id_pilih)})
                            s.commit()
                        st.success("✅ Data dihapus! Semua stok otomatis dikalkulasi ulang.")
                        st.rerun()
                    else:
                        st.error("Centang kotak konfirmasi terlebih dahulu!")
