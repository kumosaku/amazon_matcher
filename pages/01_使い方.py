import streamlit as st
from pathlib import Path

st.set_page_config(page_title="使い方", page_icon="📖", layout="wide")

# このファイル（01_使い方.py）がある場所を基準にする
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"

# 万が一見つからない場合は、カレントディレクトリも探す（デバッグ用）
if not ASSETS_DIR.exists():
     ASSETS_DIR = Path("assets").resolve()

# サイドバーに「ホームに戻る」ボタンを配置
if st.sidebar.button("🏠 ホームに戻る", type="primary"):
    st.switch_page("main.py")

st.title("📖 使い方（Amazon購入履歴 × カード明細 照合）")

st.markdown("""
## アプリ概要
このアプリは **Amazonの購入履歴CSV** と **クレジットカード明細CSV / PDF** を照合し、  
**クレジットカード明細に「Amazonで購入した商品名」を追記**するためのツールです。

## 準備するもの
- ✅ Amazon購入履歴CSV  
※(任意) Amazonのビジネス会員(無料登録可能)でない方は、Google Chrome の拡張機能「アマゾン注文履歴アシスト」を利用することで、
Amazonの注文履歴をCSV形式でダウンロードできます。
- ✅ クレジットカード利用明細（CSV or PDF）
""")

st.divider()

st.header("▶ 使用方法")

st.subheader("1. Amazon購入履歴CSVをアップロード")
st.markdown("左のサイドバー **「Amazon購入履歴(CSV)ファイルアップロード」** にアップロードします。")
img1 = ASSETS_DIR / "step1_amazon_upload.png"
if img1.exists():
    col, _ = st.columns([5, 5])
    with col:
        st.image(str(img1), caption="Amazon購入履歴CSVをアップロード", use_container_width=True)
else:
    st.warning(f"画像ファイルが見つかりません: {img1}")

st.subheader("2. クレジットカード明細をアップロード")
st.markdown("左のサイドバー **「クレジットカード明細」** で形式を選び、CSVまたはPDFをアップロードします。")
img2 = ASSETS_DIR / "step2_card_upload.png"
if img2.exists():
    col, _ = st.columns([5, 5])
    with col:
        st.image(str(img2), caption="カード明細をアップロード", use_container_width=True)

st.subheader("3.（PDFの場合）ヘッダー行の先頭列の値を選択")
st.markdown("PDFの場合は、ヘッダー行の先頭列にある値を選択してください。")
img3 = ASSETS_DIR / "step3_pdf_header.png"
if img3.exists():
    col, _ = st.columns([7, 3])
    with col:
        st.image(str(img3), caption="PDFヘッダーの選択", use_container_width=True)
else:
    st.caption("※CSVの場合は設定不要です。次へ進みます。")

st.subheader("4. 照合設定 → 照合実行")
st.markdown("「照合設定」で照合する項目を選び、**「照合実行」**ボタンをクリックします。")
img4 = ASSETS_DIR / "step4_match.png"
if img4.exists():
    col, _ = st.columns([7, 3])
    with col:
        st.image(str(img4), caption="照合設定と実行", use_container_width=True)

st.subheader("5. 照合結果を確認")
img5 = ASSETS_DIR / "step5_match.png"
if img5.exists():
    col, _ = st.columns([7, 3])
    with col:
        st.image(str(img5), caption="照合結果", use_container_width=True)

st.subheader("6. Excelをダウンロード")
st.markdown("「EXCELファイルダウンロード」ボタンで結果をダウンロードできます。")
img6 = ASSETS_DIR / "step6_DL.png"
if img6.exists():
    col, _ = st.columns([5, 5])
    with col:
        st.image(str(img6), caption="ダウンロード", use_container_width=True)
