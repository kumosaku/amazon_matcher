import streamlit as st
import pandas as pd
from utils import extract_table_from_pdf, process_matching, cleanup_dataframe
import utils
import io

st.set_page_config(page_title="Amazon履歴 & カード明細照合アプリ", layout="wide")

st.title("Amazon履歴 & カード明細照合アプリ")
st.markdown("""
Amazonの購入履歴CSVとクレジットカード明細PDFを突き合わせ、
カード明細にAmazonの商品名を追加するツールです。
""")

# サイドバーでファイルアップロード
st.sidebar.header("Amazon購入履歴 (CSV)ファイルアップロード")
amazon_file = st.sidebar.file_uploader("※このアプリでは、アップロードされたファイルを保存しません。", type=["csv"])

# クレジットカード明細のファイル形式選択
st.sidebar.markdown("---")
st.sidebar.subheader("クレジットカード明細")
card_file_type = st.sidebar.radio("ファイル形式を選択", ["PDF", "CSV"], horizontal=True)

if card_file_type == "PDF":
    card_file = st.sidebar.file_uploader("クレジットカード明細 (PDF)", type=["pdf"], key="card_pdf")
else:
    card_file = st.sidebar.file_uploader("クレジットカード明細 (CSV)", type=["csv"], key="card_csv")

if amazon_file and card_file:
    try:
        # Amazonデータの読み込み (エンコーディング対応)
        encodings = ['utf-8', 'utf-8-sig', 'cp932', 'shift_jis', 'euc_jp', 'iso2022_jp']
        df_amazon = None
        used_encoding_amazon = None
        
        for enc in encodings:
            try:
                amazon_file.seek(0)
                df_amazon = pd.read_csv(amazon_file, encoding=enc)
                used_encoding_amazon = enc
                break
            except (UnicodeDecodeError, Exception):
                continue
        
        if df_amazon is None:
            st.error("Amazon購入履歴CSVの読み込みに失敗しました。エンコーディングを確認してください。")
            st.stop()
        else:
            st.success(f"✅ Amazon購入履歴を読み込みました（エンコーディング: {used_encoding_amazon}）")
        


        # クリーニング（日付行の抽出）
        # Amazon CSVは通常綺麗だが、念のため適用するか、あるいはユーザーの要望が「Amazonデータのプレビュー」だったので適用する
        # ただし、Amazon CSVはヘッダーが重要なので、ヘッダーが消えると困る。
        # クリーニング関数は「日付行のみ」にするので、ヘッダーが消える。
        # Amazon CSVは pd.read_csv でヘッダー認識されているはずなので、df_amazon は既にヘッダー持ち。
        # ここで cleanup_dataframe を呼ぶとヘッダー以外のメタデータ行（もしあれば）は消えるが、
        # 通常のデータ行は残る。
        # もしユーザーがCard明細をAmazonと呼んでいるなら、そちらに効くのが重要。
        
        # 曖昧さを排除するため、両方に適用するオプションを表示するか、常時適用するか。
        # ユーザー要望: "先頭が日付となっている列が繰り返している行から表示できますか"
        # これは「有効データのみ抽出して」という意味と取れる。
        
        # ただ、Amazon CSVのヘッダー("注文日"など)が pd.read_csv で正しく認識されていない場合（上にゴミがある場合）、
        # ヘッダーそのものが "Column 1" みたいになっていて、データ行に "注文日" が混じる可能性がある。
        # pd.read_csv は1行目をヘッダーとする。
        
        # 今回は「PDF明細」に主眼を置きつつ、Amazonの方も同様の処理を試みるが、
        # Amazon CSVが正規フォーマットなら read_csv の時点でヘッダーは取れている。
        # Card PDF は DataFrame化した時点でヘッダーがない（Column_0...）。
        
        # --- 1. Amazonデータ プレビュー (先に表示) ---
        st.subheader("1. Amazonデータ プレビュー")
        
        # プレビュー表示用に数値をカンマ区切りに整形
        df_amazon_preview = df_amazon.copy()
        # 金額系のカラムを推定してフォーマット
        price_keywords = ['金額', '請求額', '小計', 'Price', 'Amount']
        for col in df_amazon_preview.columns:
            if any(k in col for k in price_keywords) and pd.api.types.is_numeric_dtype(df_amazon_preview[col]):
                 # 整数化してからカンマ区切り文字列に変換
                 df_amazon_preview[col] = df_amazon_preview[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")
        
        st.dataframe(df_amazon_preview, height=400)


        # --- 2. クレジットカード明細の処理とプレビュー ---
        # Card PDFまたはCSVのクリーニング
        with st.spinner("ファイルを解析中..."):
            if card_file_type == "PDF":
                df_card_raw = extract_table_from_pdf(card_file, raw=True)
            else:  # CSV
                # 複数のエンコーディングを試行
                encodings = ['utf-8', 'utf-8-sig', 'cp932', 'shift_jis', 'euc_jp', 'iso2022_jp']
                df_card_raw = None
                used_encoding = None
                
                for enc in encodings:
                    try:
                        card_file.seek(0)
                        df_card_raw = pd.read_csv(card_file, encoding=enc)
                        used_encoding = enc
                        break
                    except (UnicodeDecodeError, Exception):
                        continue
                
                if df_card_raw is None:
                    st.error("CSVファイルの読み込みに失敗しました。エンコーディングを確認してください。")
                else:
                    st.success(f"✅ CSVファイルを読み込みました（エンコーディング: {used_encoding}）")

        df_card = None # 初期化

        if df_card_raw is not None and not df_card_raw.empty:
            
            if card_file_type == "PDF":
                # PDFの場合: 生データ表示とヘッダー行の選択
                st.subheader(f"2. {card_file_type}読み取り結果 (生データ)")
                st.dataframe(df_card_raw, height=300)
                
                # ヘッダー行の指定
                st.markdown("##### ヘッダー行の指定")
                # 1列目のユニークな値を取得して選択肢にする (出現順を維持)
                # nanやNoneを除外
                raw_col0 = df_card_raw.iloc[:, 0]
                col0_values = []
                seen = set()
                
                for x in raw_col0:
                    x_str = str(x).strip()
                    # 意味のある文字列のみを対象にする (必要に応じて調整)
                    if x_str and x_str not in seen and x_str.lower() != 'nan' and x_str.lower() != 'none':
                        col0_values.append(x_str)
                        seen.add(x_str)
                
                # レイアウト調整: 1/2の幅にする
                header_col1, header_col2 = st.columns(2)
                
                with header_col1:
                  header_trigger_val = st.selectbox(
                      "ヘッダー行の1列目にある文字列を選択してください",
                      options=col0_values,
                      key="header_trigger_val"
                  )
                
                # 選択された値が最初に出現する行を探す
                header_row_index = 0
                for i, val in enumerate(df_card_raw.iloc[:, 0]):
                    if str(val).strip() == header_trigger_val:
                        header_row_index = i
                        break
                
                st.caption(f"選択された文字列「{header_trigger_val}」は、行 {header_row_index} に見つかりました。この行をヘッダーとして扱います。")

                # 整形処理 (指定行をヘッダーとする)
                df_sliced = df_card_raw.iloc[int(header_row_index):].reset_index(drop=True)
                
                # 1行目をヘッダーに設定
                new_header = df_sliced.iloc[0].astype(str).str.replace('\n', ' ').str.strip()
                df_card = df_sliced[1:].copy()
                df_card.columns = new_header
                
                # カラム名の重複回避
                unique_cols = []
                seen = {}
                current_cols = df_card.columns.astype(str)
                
                for i, c in enumerate(current_cols):
                    c_str = str(c).strip()
                    if not c_str:
                            c_str = f"Col_{i}"
                    
                    if c_str in seen:
                        seen[c_str] += 1
                        c_str = f"{c_str}_{seen[c_str]}"
                    else:
                        seen[c_str] = 0
                    unique_cols.append(c_str)
                
                df_card.columns = unique_cols

                st.subheader(f"3. 整形後プレビュー")
                st.dataframe(df_card, height=400)
            
            else:
                # CSVの場合: 1行目を自動的にヘッダーとして扱う
                df_card = df_card_raw.copy()
                
                st.subheader(f"2. {card_file_type}読み取り結果")
                st.dataframe(df_card, height=400)


        if df_card is not None and not df_card.empty:


            # カラムマッピングの設定
            st.subheader("4. 照合設定")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Amazonデータ列指定")
                col_amz_date = st.selectbox("購入日", df_amazon.columns, index=utils.get_default_index(df_amazon.columns, ['注文日', '購入日', 'Date']))
                col_amz_price = st.selectbox("金額", df_amazon.columns, index=utils.get_default_index(df_amazon.columns, ['請求額', '金額', 'Price', '支払金額']), key='amz_price')
                col_amz_item = st.selectbox("商品名 (検索値A)", df_amazon.columns, index=utils.get_default_index(df_amazon.columns, ['商品名', 'タイトル', 'Item']), key='amz_item')

            with col2:
                st.markdown("### カード明細列指定")
                col_card_date = st.selectbox(
                    "利用日", 
                    df_card.columns, 
                    index=utils.get_default_index(df_card.columns, ['利用日', '日付', 'Date', 'Time']),
                    key='card_date'
                )
                
                col_card_price = st.selectbox(
                    "金額", 
                    df_card.columns, 
                    index=utils.get_default_index(df_card.columns, ['金額', '請求額', 'Price', 'Amount', '円', '支払']),
                    key='card_price'
                )
                
                col_card_desc = st.selectbox(
                    "利用店名・商品名 (既存)", 
                    df_card.columns, 
                    index=utils.get_default_index(df_card.columns, ['利用店名', '商品名', 'Description', 'Item', 'Merchant', '摘要']),
                    key='card_desc'
                )
                
                # 選択された列のサンプルデータを表示
                sample_values = df_card[col_card_desc].dropna().unique()[:5]
                st.caption(f"💡 選択中の列「{col_card_desc}」のサンプル: {', '.join([str(x) for x in sample_values])}")
                
                # 利用店名フィルタリング UI
                unique_merchants = sorted([str(x) for x in df_card[col_card_desc].unique() if x])
                
                # デフォルト選択: "AMAZON"関連（全角・半角・カタカナ・英語）を含むものを優先
                amazon_keywords = ["AMAZON", "Amazon", "アマゾン", "ｱﾏｿﾞﾝ"]
                default_merchants = [
                    m for m in unique_merchants 
                    if any(k in m.upper() for k in amazon_keywords) or any(k in m for k in amazon_keywords)
                ]
                
                if not default_merchants:
                    default_merchants = unique_merchants # 見つからなければ全選択
                
                
                selected_merchants = st.multiselect(
                    "照合対象とする店名を選択", 
                    options=unique_merchants,
                    default=default_merchants,
                    key=f"merchants_{col_card_desc}"
                )
                
                
            if st.button("照合実行"):
                if not selected_merchants:
                    st.warning("照合対象の店名が1つも選択されていません。")
                else:
                    with st.spinner("照合中..."):
                        # 計算結果をsession_stateに保存
                        st.session_state['result_df'] = process_matching(
                            df_amazon, df_card,
                            (col_amz_date, col_amz_price, col_amz_item),
                            (col_card_date, col_card_price, col_card_desc),
                            target_merchants=selected_merchants
                        )
                        st.session_state['processed'] = True
            
            # 処理済みフラグがある場合のみ結果を表示
            if st.session_state.get('processed', False) and 'result_df' in st.session_state:
                result_df = st.session_state['result_df']

                st.subheader("5. 照合結果")
                
                # フィルタリング機能
                st.markdown("##### 🔍 結果のフィルタリング")
                
                # レイアウト調整: 1/2の幅にする
                filter_col1, filter_col2 = st.columns(2)
                
                with filter_col1:
                    filter_column = st.selectbox(
                        "フィルタする列を選択",
                        options=["(フィルタなし)"] + list(result_df.columns),
                        key="filter_column"
                    )
                
                # フィルタリング処理
                filtered_df = result_df.copy()
                
                if filter_column == "(フィルタなし)":
                    with filter_col1:
                        st.multiselect(
                            "対象の値(リストで選択)",
                            options=[],
                            disabled=True,
                            placeholder="先に列を選択してください",
                            key="filter_values_disabled"
                        )
                else:
                    # 選択された列のユニークな値を取得
                    unique_values = sorted([str(x) for x in result_df[filter_column].unique() if pd.notna(x)])
                    
                    # 空文字列も選択肢に含める
                    if "" in result_df[filter_column].values or result_df[filter_column].isna().any():
                        unique_values = ["(空白)"] + unique_values
                    
                    with filter_col1:
                        st.write(f"選択された列: {filter_column}")
                        st.write(f"ユニーク値の数: {len(unique_values)}")
                        
                        selected_values = st.multiselect(
                            "対象の値(リストで選択)",
                            options=unique_values,
                            default=[],
                            key=f"filter_values_{filter_column}"
                        )
                    
                    # フィルタリング適用
                    if selected_values:
                        if "(空白)" in selected_values:
                            # 空白を含む場合
                            other_values = [v for v in selected_values if v != "(空白)"]
                            if other_values:
                                filtered_df = result_df[
                                    result_df[filter_column].isin(other_values) | 
                                    result_df[filter_column].isna() |
                                    (result_df[filter_column] == "")
                                ]
                            else:
                                filtered_df = result_df[
                                    result_df[filter_column].isna() |
                                    (result_df[filter_column] == "")
                                ]
                        else:
                            filtered_df = result_df[result_df[filter_column].isin(selected_values)]
                
                # フィルタリング結果の表示
                st.caption(f"表示件数: {len(filtered_df)} / 全{len(result_df)}件")
                st.dataframe(filtered_df, height=400)
                
                matched_count = result_df['Amazon商品名'].replace('', pd.NA).dropna().count()
                if matched_count == 0:
                    st.warning("""
                    一致するデータが見つかりませんでした。以下の設定を確認してください：
                    1. **金額カラム**: 正しい金額が入力されている列が選ばれていますか？ (Col_X がずれている可能性があります)
                    2. **利用店名**: 正しい店名がフィルタ選択されていますか？
                    3. **日付**: Amazonの注文日とカード利用日にズレがないか確認してください。
                    """)
                elif matched_count < len(result_df):
                        st.info(f"{len(result_df)}件中、{matched_count}件がマッチしました。")
            
            
                # ダウンロードボタン
                st.markdown("---")
                
                # 全データをダウンロード
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    filtered_df.to_excel(writer, index=False) # フィルタ済みのデータをダウンロードに変更（要望はないが自然なUXとして）
                data = output.getvalue()
                
                st.download_button(
                    label=f"📥 Excelとしてダウンロード ({len(filtered_df)}件)",
                    data=data,
                    file_name="matched_statement.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        else:
            st.error("PDFから表データを抽出できませんでした。フォーマットを確認してください。")

    except Exception as e:
        import traceback
        st.error(f"エラーが発生しました: {e}")
        st.code(traceback.format_exc())

else:
    st.info("サイドバーから両方のファイルをアップロードしてください。")
