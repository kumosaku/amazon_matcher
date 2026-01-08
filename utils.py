import pdfplumber
import pandas as pd
import re

def extract_table_from_pdf(pdf_file, raw=False):
    """
    PDFファイルから表データを抽出し、DataFrameとして返す。
    pdfplumberを使用し、lattice（罫線）とstream（空白）の両方の戦略を試す。
    raw=Trueの場合、ヘッダー処理を行わずにそのままDataFrameを返す。
    """
    all_rows = []
    
    try:
        with pdfplumber.open(pdf_file) as pdf:
            temp_rows = []
            
            for page in pdf.pages:
                if raw:
                    # Rawモード: テキスト全体を抽出（layout=Trueで視覚的配置を維持）
                    # extract_textは表の外にある文字も拾ってくれる
                    text = page.extract_text(layout=True)
                    if text:
                        for line in text.split('\n'):
                             # 連続する空白を区切りとみなす (regexで2文字以上の空白)
                             # strip()してしまうと文頭のインデント情報が消えるが、
                             # DataFrameに入れるなら値としての区切りが重要なのでstripしてから分割する
                             parts = re.split(r'\s{2,}', line.strip())
                             # 空行でなければ追加
                             if any(parts) and "".join(parts).strip():
                                 temp_rows.append(parts)
                else:
                    # 通常モード: テーブル抽出
                    # 戦略1: デフォルト (設定なし)
                    # 戦略2: lattice (罫線重視)
                    # 戦略3: stream (空白重視)
                    
                    tables = page.extract_tables()
                    
                    # テーブルが見つからない、または行数が少ない場合は設定を変えてみる
                    if not tables:
                        tables = page.extract_tables(table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"}) # stream like
                    
                    if not tables:
                            tables = page.extract_tables(table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"}) # lattice like

                    for table in tables:
                        for row in table:
                            # セルの中身をクリーニング
                            clean_row = []
                            for cell in row:
                                if cell is None:
                                    clean_cell = ""
                                else:
                                    # 通常時は改行除去
                                    clean_cell = str(cell).replace('\n', ' ').strip()
                                
                                clean_row.append(clean_cell)
                            
                            # 空でない行のみ追加
                            if any(clean_row):
                                temp_rows.append(clean_row)
            
            all_rows = temp_rows

    except Exception as e:
        # エラー発生時は呼び出し元で表示できるように再度st.error等を使いたいが、
        # ここは純粋関数なのでエラーじみたDataFrameを返すか、例外をそのまま上げる
        # 呼び出し元でcatchしているのでraiseする
        raise e

    if not all_rows:
        return pd.DataFrame()

    # データ整形ロジック
    # 最大列数に合わせてパディング
    max_cols = max(len(row) for row in all_rows)
    adjusted_rows = [row + [""] * (max_cols - len(row)) for row in all_rows]
    
    if raw:
        return pd.DataFrame(adjusted_rows)
    
    # 1行目をヘッダーと仮定
    header = adjusted_rows[0]
    data = adjusted_rows[1:]
    
    # カラム名の重複回避
    unique_header = []
    seen = {}
    for i, col in enumerate(header):
        col_name = col if col else f"Column_{i}"
        if col_name in seen:
            seen[col_name] += 1
            col_name = f"{col_name}_{seen[col_name]}"
        else:
            seen[col_name] = 0
        unique_header.append(col_name)

    df = pd.DataFrame(data, columns=unique_header)
    return df

import unicodedata

def cleanup_dataframe(df):
    """
    データフレームから、日付で始まる（あるいは日付を含む）行を探して、
    有効な明細データと思われる行のみを抽出・再構成する。
    
    実装戦略 (Anchor方式):
    スペース区切りだと「商品名」の中にスペースがある場合に列がずれる問題がある。
    そのため、比較的構造が安定している「日付」と「支払い方法(例: 1回払い)」をアンカーとして
    その間を「商品名」として抽出する。
    
    構成: [日付] [商品名] [支払い方法] [金額1] [金額2] ...
    """
    if df.empty:
        return df

    # 日付列特定
    date_pattern = re.compile(r'(\d{4}/\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2})')
    best_date_col_idx = -1
    max_match_count = 0
    
    # 全列探索
    for col_idx in range(len(df.columns)):
        col_data = df.iloc[:, col_idx].astype(str)
        match_count = col_data.str.contains(date_pattern, regex=True).sum()
        if match_count > max_match_count:
            max_match_count = match_count
            best_date_col_idx = col_idx
            
    if best_date_col_idx == -1:
        return df

    date_col_name = df.columns[best_date_col_idx]
    
    # 日付を含む行のみ抽出
    raw_series = df[date_col_name].astype(str)
    is_date_row = raw_series.str.contains(date_pattern, regex=True)
    target_df = df[is_date_row].copy()
    
    new_rows = []
    
    # 支払い方法などの中間マーカーを探す正規表現
    # 例: "1回払い", "2回払い", "リボ払い", "ボーナス一括払い" など
    # 具体的なデータから "1回払い" が多いが、汎用性を持たせる
    payment_pattern = re.compile(r'(\d+回払い|リボ払い|ボーナス\S*払い)')
    
    for _, row in target_df.iterrows():
        # 行全体のテキストを再構築
        cells = []
        for col_val in row[best_date_col_idx:]:
            if col_val is not None:
                s = str(col_val).strip()
                if s:
                    cells.append(s)
        full_text = " ".join(cells)
        
        # 正規化
        text = unicodedata.normalize('NFKC', full_text)
        
        # パース処理
        # 1. 先頭の日付を抽出
        date_match = date_pattern.search(text)
        if not date_match:
            continue # 日付がない（フィルタ済みのはずだが念のため）
            
        date_str = date_match.group(1)
        remaining_text = text[date_match.end():].strip()
        
        # 2. 中間マーカー（支払い方法）を探す
        payment_match = payment_pattern.search(remaining_text)
        
        row_data = [date_str]
        
        if payment_match:
            # マーカーがあれば、そこまでが商品名
            desc = remaining_text[:payment_match.start()].strip()
            payment_method = payment_match.group(1)
            after_payment = remaining_text[payment_match.end():].strip()
            
            row_data.append(desc)
            row_data.append(payment_method)
            
            # マーカー以降は金額などがスペース区切りで続くと想定
            # 全角スペースなどもタブに変換して分割
            # ここではシンプルに空白分割 (カンマは金額に含まれるため区切り文字から除外)
            others = [p.strip() for p in re.split(r'[ \u3000\t]+', after_payment) if p.strip()]
            row_data.extend(others)
            
        else:
            # マーカーが見つからない場合（AMAZONなどで支払い方法がない場合など？）
            # 単純にスペース分割で頑張る、あるいは残り全て商品名とする？
            # ユーザー例では "1回払い" があったので、とりあえずスペース分割して
            # 2列目を商品名とする（従来ロジックに近い形）
            parts = [p.strip() for p in re.split(r'[ \u3000\t]+', remaining_text) if p.strip()]
            row_data.extend(parts)
            
        new_rows.append(row_data)
        
    if not new_rows:
        return pd.DataFrame()

    # 最大列数
    max_cols = max(len(row) for row in new_rows)
    adjusted_rows = [row + [""] * (max_cols - len(row)) for row in new_rows]
    
    # カラム名生成
    new_cols = [f"Col_{i+1}" for i in range(max_cols)]
    if len(new_cols) >= 3:
        new_cols[0] = "抽出日付"
        new_cols[1] = "抽出利用店名"
        new_cols[2] = "抽出支払方法"

    new_df = pd.DataFrame(adjusted_rows, columns=new_cols)
    
    return new_df

def normalize_date(date_series):
    """
    日付表記を統一する（YYYY/MM/DD形式など）
    """
    # 025/11/26 みたいな誤認識（先頭欠け）を補正する簡易ロジック
    # 3桁の年号の場合は20をつけるなど（今は2025年付近と想定）
    def fix_date_str(x):
        s = str(x).strip()
        # 025/ -> 2025/
        if re.match(r'^0\d{2}/', s):
            return '2' + s
        return s

    fixed_series = date_series.apply(fix_date_str)
    return pd.to_datetime(fixed_series, errors='coerce')

def normalize_price(price_series):
    """
    金額表記を数値に変換する（カンマ除去など）
    """
    # 文字列型に変換してから処理
    return pd.to_numeric(
        price_series.astype(str).str.strip().str.replace(',', '').str.replace('¥', '').str.replace('円', ''), 
        errors='coerce'
    )

def process_matching(df_amazon, df_card, amz_cols, card_cols, target_merchants=None):
    """
    Amazonデータとカード明細を照合する
    amz_cols: (date, price, item)
    card_cols: (date, price, desc)
    target_merchants: 照合対象とする利用店名のリスト (Noneの場合は全件)
    """
    amz_date_col, amz_price_col, amz_item_col = amz_cols
    card_date_col, card_price_col, card_desc_col = card_cols

    # コピー作成してデータ加工
    df_amz_proc = df_amazon.copy()
    df_card_proc = df_card.copy()

    # 型変換と正規化
    df_amz_proc['norm_date'] = normalize_date(df_amz_proc[amz_date_col])
    df_amz_proc['norm_price'] = normalize_price(df_amz_proc[amz_price_col])
    
    df_card_proc['norm_date'] = normalize_date(df_card_proc[card_date_col])
    df_card_proc['norm_price'] = normalize_price(df_card_proc[card_price_col])

    # 照合処理
    # カード明細をループして、Amazon履歴から該当するものを探す（簡易ロジック）
    # 日付と金額が完全一致するものを探す
    
    matched_items = []
    
    for idx, row in df_card_proc.iterrows():
        c_date = row['norm_date']
        c_price = row['norm_price']
        
        if pd.isna(c_date) or pd.isna(c_price):
            matched_items.append("")
            continue

        # フィルタリング: 対象の店名でない場合はスキップ
        if target_merchants is not None:
            current_desc = str(row[card_desc_col])
            if current_desc not in target_merchants:
                 matched_items.append("") # 対象外
                 continue

        # 一致検索
        matches = df_amz_proc[
            (df_amz_proc['norm_date'] == c_date) & 
            (abs(df_amz_proc['norm_price']) == abs(c_price)) # 金額は絶対値で比較（支払いはマイナス表記の場合もあるため）
        ]
        
        if not matches.empty:
            # 複数ヒットした場合は最初の商品名、あるいは連結するなどの処理
            # ここでは最初の商品名を取得
            item_name = matches.iloc[0][amz_item_col]
            matched_items.append(item_name)
        else:
            matched_items.append("")

    # 結果を元のカード明細に追加
    # 「クレジットカード明細」という名前で列を追加する要求だが、
    # 既存の明細に「品名」を追加するという意味と解釈
    result_df = df_card.copy()
    result_df['Amazon商品名'] = matched_items
    
    return result_df

def get_default_index(columns, candidates, check_numeric=False, df=None):
    # 1. 完全一致で検索
    for candidate in candidates:
        if candidate in columns:
            return columns.get_loc(candidate)
            
    # 2. 部分一致で検索 (候補文字列がカラム名に含まれているか)
    for candidate in candidates:
        for i, col in enumerate(columns):
            if candidate in str(col):
                return i
    return 0
    
    # 数値列かどうかで判定 (金額カラムの推定)
    if check_numeric and df is not None:
            for i, col in enumerate(columns):
                # 列名が "Col_" で始まる場合、中身が数値っぽいか確認
                if col.startswith("Col_"):
                    try:
                        # サンプル数行をチェック
                        sample = df[col].dropna().head(10).astype(str).str.replace(',', '').str.replace('¥', '')
                        # 8割以上が数値なら候補とする
                        numeric_count = pd.to_numeric(sample, errors='coerce').notna().sum()
                        if len(sample) > 0 and (numeric_count / len(sample)) > 0.8:
                            return i
                    except:
                        pass
    return 0
