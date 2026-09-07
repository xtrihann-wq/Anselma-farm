import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime, date
import io

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Anselma Farm - PuyuhKu", layout="wide", page_icon="🐣")

# ==========================================
# 2. SISTEM DATABASE (SQLITE LOKAL AMAN)
# ==========================================
DB_PATH = "anselma_farm.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS produksi 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, Tanggal TEXT, Populasi_Aktif INTEGER, Mortalitas INTEGER, 
                  Telur_Butir INTEGER, Telur_Kg REAL, Pakan_Kg REAL)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS kasir 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, Tanggal TEXT, Varian TEXT, Harga_Satuan INTEGER, 
                  Kuantitas INTEGER, Total_Rp INTEGER)''')
                 
    c.execute('''CREATE TABLE IF NOT EXISTS pengeluaran 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, Tanggal TEXT, Kategori TEXT, Deskripsi TEXT, Nominal_Rp INTEGER)''')
    conn.commit()
    conn.close()

def get_data(table_name):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df

init_db()

VARIAN_TELUR = {
    "Per Kilo (1 kg)": 33000,
    "Tengahan (0.5 kg)": 16500,
    "Seperempat (0.25 kg)": 9000
}

# ==========================================
# 3. NAVIGASI SIDEBAR
# ==========================================
try:
    st.sidebar.image("logo.jpeg", use_container_width=True)
except:
    pass 

st.sidebar.title("Anselma Farm")
st.sidebar.markdown("Sistem Manajemen Tersimpan")
menu = st.sidebar.radio("Menu Navigasi:", [
    "📊 Dashboard & Prediksi", 
    "📝 Catat Produksi Harian", 
    "🛒 Kasir / Penjualan", 
    "💸 Pencatatan Pengeluaran", 
    "📁 Export Excel (Rapi)",
    "🗑️ Hapus Data Salah"
])

# ==========================================
# 4. LOGIKA HALAMAN & UI
# ==========================================

# --- HALAMAN DASHBOARD ---
if menu == "📊 Dashboard & Prediksi":
    st.title("📊 Dashboard Utama Anselma Farm")
    
    df_prod = get_data('produksi')
    df_kasir = get_data('kasir')
    df_peng = get_data('pengeluaran')
    
    # 1. Ringkasan Angka (Metrik)
    total_telur_kg = df_prod["Telur_Kg"].sum() if not df_prod.empty else 0
    total_pakan_kg = df_prod["Pakan_Kg"].sum() if not df_prod.empty else 0
    fcr = (total_pakan_kg / total_telur_kg) if total_telur_kg > 0 else 0
    
    total_pemasukan = df_kasir["Total_Rp"].sum() if not df_kasir.empty else 0
    total_pengeluaran = df_peng["Nominal_Rp"].sum() if not df_peng.empty else 0
    laba_bersih = total_pemasukan - total_pengeluaran

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Produksi", f"{total_telur_kg:.2f} Kg")
    with col2: st.metric("Rasio Pakan (FCR)", f"{fcr:.2f}")
    with col3: st.metric("Total Pemasukan", f"Rp {total_pemasukan:,.0f}")
    with col4: st.metric("Laba Bersih", f"Rp {laba_bersih:,.0f}")

    st.divider()
    
    # 2. GRAFIK STATISTIK ARUS KAS UTAMA
    st.subheader("💰 Statistik Arus Kas (Pemasukan vs Pengeluaran)")
    
    if not df_kasir.empty or not df_peng.empty:
        # Menyiapkan data Pemasukan
        if not df_kasir.empty:
            kasir_harian = df_kasir.groupby('Tanggal')['Total_Rp'].sum().reset_index()
            kasir_harian.rename(columns={'Total_Rp': 'Pemasukan'}, inplace=True)
        else:
            kasir_harian = pd.DataFrame(columns=['Tanggal', 'Pemasukan'])
            
        # Menyiapkan data Pengeluaran
        if not df_peng.empty:
            peng_harian = df_peng.groupby('Tanggal')['Nominal_Rp'].sum().reset_index()
            peng_harian.rename(columns={'Nominal_Rp': 'Pengeluaran'}, inplace=True)
        else:
            peng_harian = pd.DataFrame(columns=['Tanggal', 'Pengeluaran'])
            
        # Menggabungkan data berdasarkan tanggal
        df_arus_kas = pd.merge(kasir_harian, peng_harian, on='Tanggal', how='outer').fillna(0)
        df_arus_kas = df_arus_kas.sort_values('Tanggal').set_index('Tanggal')
        
        # Menampilkan grafik batang (Hijau = Masuk, Merah = Keluar)
        st.bar_chart(df_arus_kas, color=["#2ECC71", "#E74C3C"]) 
    else:
        st.info("Belum ada data transaksi keuangan untuk ditampilkan.")

    st.divider()

    # 3. GRAFIK PENDUKUNG (PRODUKSI & KATEGORI PENGELUARAN)
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("📈 Tren Produksi Telur (Kg)")
        if not df_prod.empty:
            chart_prod = df_prod.groupby("Tanggal")["Telur_Kg"].sum()
            st.line_chart(chart_prod, color="#F1C40F") # Warna kuning/emas
        else:
            st.info("Belum ada data produksi telur.")
            
    with col_chart2:
        st.subheader("📉 Distribusi Pengeluaran")
        if not df_peng.empty:
            # Mengelompokkan pengeluaran berdasarkan kategorinya
            peng_kategori = df_peng.groupby('Kategori')['Nominal_Rp'].sum()
            st.bar_chart(peng_kategori, color="#9B59B6") # Warna ungu
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
            pakan = st.number_input("Konsumsi Pakan (Kg)", min_value=0.0, format="%.2f")
            
        if st.form_submit_button("Simpan Data"):
            pop_aktif = populasi - mati
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO produksi (Tanggal, Populasi_Aktif, Mortalitas, Telur_Butir, Telur_Kg, Pakan_Kg) VALUES (?,?,?,?,?,?)", 
                      (str(tgl), pop_aktif, mati, telur_butir, telur_kg, pakan))
            conn.commit()
            conn.close()
            st.success("✅ Data tersimpan aman!")
            
    st.dataframe(get_data('produksi').tail(5), use_container_width=True)

# --- HALAMAN KASIR ---
elif menu == "🛒 Kasir / Penjualan":
    st.title("🛒 Kasir Penjualan")
    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("form_kasir", clear_on_submit=True):
            tgl_kasir = st.date_input("Tanggal Transaksi", date.today())
            varian = st.selectbox("Pilih Varian Berat", list(VARIAN_TELUR.keys()))
            kuantitas = st.number_input("Kuantitas (Jumlah)", min_value=1, value=1)
            
            if st.form_submit_button("Bayar & Simpan"):
                harga_satuan = VARIAN_TELUR[varian]
                total_harga = harga_satuan * kuantitas
                
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("INSERT INTO kasir (Tanggal, Varian, Harga_Satuan, Kuantitas, Total_Rp) VALUES (?,?,?,?,?)", 
                          (str(tgl_kasir), varian, harga_satuan, kuantitas, total_harga))
                conn.commit()
                conn.close()
                st.success(f"✅ Transaksi sukses! Total: Rp {total_harga:,.0f}")
                
    with col2:
        st.dataframe(get_data('kasir').tail(5), use_container_width=True)

# --- HALAMAN PENGELUARAN ---
elif menu == "💸 Pencatatan Pengeluaran":
    st.title("💸 Catat Arus Kas Keluar")
    with st.form("form_pengeluaran", clear_on_submit=True):
        tgl_peng = st.date_input("Tanggal", date.today())
        kategori = st.selectbox("Kategori", ["Beli Pakan", "Vitamin/Obat", "Gaji Karyawan", "Listrik & Air", "Lainnya"])
        deskripsi = st.text_input("Keterangan")
        nominal = st.number_input("Nominal (Rp)", min_value=0, step=10000)
        
        if st.form_submit_button("Simpan Pengeluaran"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO pengeluaran (Tanggal, Kategori, Deskripsi, Nominal_Rp) VALUES (?,?,?,?)", 
                      (str(tgl_peng), kategori, deskripsi, nominal))
            conn.commit()
            conn.close()
            st.success("✅ Pengeluaran tercatat!")
            
    st.dataframe(get_data('pengeluaran').tail(5), use_container_width=True)

# --- HALAMAN EXPORT EXCEL ---
elif menu == "📁 Export Excel (Rapi)":
    st.title("📁 Export Data ke Excel")
    
    if st.button("🔄 Generate File Excel"):
        df_prod = get_data('produksi')
        df_kasir = get_data('kasir')
        df_peng = get_data('pengeluaran')
        
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
                    if 'Rp' in col or col in ['Harga_Satuan', 'Total_Rp', 'Nominal_Rp']:
                        worksheet.set_column(i, i, max_len, format_rp)
                    elif 'Kg' in col or col in ['Telur_Kg', 'Pakan_Kg']:
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

# --- HALAMAN HAPUS DATA ---
elif menu == "🗑️ Hapus Data Salah":
    st.title("🗑️ Hapus Pencatatan yang Salah")
    
    tabel_pilihan = st.selectbox("Pilih Kategori:", ["produksi", "kasir", "pengeluaran"])
    df_hapus = get_data(tabel_pilihan)
    
    if df_hapus.empty:
        st.info(f"Belum ada data pada kategori {tabel_pilihan}.")
    else:
        st.dataframe(df_hapus, use_container_width=True)
        with st.form("form_hapus"):
            id_hapus = st.selectbox("Pilih ID Data yang ingin dihapus:", df_hapus["id"].tolist())
            konfirmasi = st.checkbox("Saya yakin ingin menghapus data ini")
            
            if st.form_submit_button("🚨 Hapus Data Sekarang"):
                if konfirmasi:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute(f"DELETE FROM {tabel_pilihan} WHERE id = ?", (id_hapus,))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Data dengan ID {id_hapus} berhasil dihapus!")
                    st.rerun()
                else:
                    st.error("Centang kotak konfirmasi terlebih dahulu!")
