# -*- coding: utf-8 -*-
"""
💌 表白禮物比價系統（Streamlit）
1. 設定表白對象與預算
2. 同時搜尋 PChome × momo，比價並挑選禮物
3. 產生表白文字（可自行修改）
4. 產生專屬表白連結：對方打開就會看到卡片、禮物與「願意和我在一起嗎？」
"""
import html
import re
import time
from urllib.parse import urlencode

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="表白禮物比價系統", page_icon="💌", layout="wide")

# ------------------------------------------------------------------
# 常數
# ------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    )
}
PCHOME_API = "https://ecshweb.pchome.com.tw/search/v3.3/all/results"
MOMO_API = "https://apisearch.momoshop.com.tw/momoSearchCloud/moec/textSearch"
PLATFORMS = ["PChome", "momo"]
COLORS = {"PChome": "#E8590C", "momo": "#7048E8"}
ALLOWED_LINK_PREFIX = (
    "https://24h.pchome.com.tw/",
    "https://www.momoshop.com.tw/",
)

GIFT_PRESETS = [
    "花束", "巧克力禮盒", "泰迪熊", "香水", "項鍊", "手作蛋糕",
    "情侶對戒", "保溫杯", "永生花", "自訂…",
]

TEMPLATES = {
    "浪漫": [
        "{to}，\n遇見你之後，平凡的日子都變得閃閃發亮。\n我想把每個早晨的第一句問候、每個夜晚的最後一句晚安，都留給你。\n\n我喜歡你，很喜歡很喜歡。\n—— {frm}",
        "{to}，\n如果世界是一本書，我希望每一頁都有你。\n謝謝你出現在我的生命裡，讓我學會心動的感覺。\n\n可以讓我用往後的日子，慢慢告訴你我有多喜歡你嗎？\n—— {frm}",
    ],
    "可愛": [
        "{to}～\n我偷偷觀察你很久了，結論是：你超可愛！\n我的心跳每次看到你都會自動加速，連我自己都管不住。\n\n所以，要不要考慮收留我呀？🥺\n—— {frm}",
        "嗨 {to}，\n我發現我每天最期待的事情，就是可以跟你聊天。\n如果喜歡你是一種病，那我大概已經無藥可救了。\n\n你願意當我的解藥嗎？\n—— {frm}",
    ],
    "真誠": [
        "{to}，\n我不太會說漂亮的話，但我想認真地告訴你：我喜歡你。\n喜歡你的笑容、你認真的樣子，還有和你相處時的自在。\n\n不管你的答案是什麼，我都很感謝你願意聽我說完。\n—— {frm}",
        "{to}，\n這段時間和你相處，我越來越確定自己的心意。\n我想成為那個能陪你分享開心、也能陪你度過低潮的人。\n\n如果你也願意，我們可以試著在一起嗎？\n—— {frm}",
    ],
    "幽默": [
        "{to}，\n我查過了，你的名字和我的未來規劃出現在同一個檔案裡。\n經過嚴謹的評估，我決定喜歡你，而且沒有備案。\n\n請問你願意通過這份「交往申請」嗎？\n—— {frm}",
        "{to}，\n我最近一直在想一個問題：怎麼可以有人這麼剛好，剛好是我喜歡的樣子？\n所以我決定鼓起勇氣，把這份心意交給你。\n\n（備註：本人有保固，終身免費維修。）\n—— {frm}",
    ],
}

NO_LABELS = ["再想想…", "真的要再想想嗎？🥺", "再給我一次機會嘛～", "我還沒準備好 🌱"]
NO_REPLIES = [
    "",
    "（偷偷把心跳調大聲）",
    "（小聲）我會很認真地對你好的……",
    "",
]


# ------------------------------------------------------------------
# 爬蟲：PChome / momo
# ------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def fetch_pchome_page(keyword: str, page: int) -> dict:
    params = {"q": keyword, "page": page, "sort": "sale/dc"}
    resp = requests.get(PCHOME_API, params=params, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.json()


def build_momo_payload(keyword: str, page: int) -> dict:
    return {
        "host": "momoshop",
        "flag": "searchEngine",
        "data": {
            "specialGoodsType": "", "isBrandSeriesPage": "false", "authorNo": "",
            "originalCateCode": "", "cateType": "", "searchValue": keyword,
            "cateCode": "", "cateLevel": "-1", "cp": "N", "NAM": "N", "first": "N",
            "freeze": "N", "superstore": "N", "tvshop": "N", "china": "N",
            "tomorrow": "N", "stockYN": "N", "prefere": "N", "threeHours": "N",
            "video": "N", "cycle": "N", "cod": "N", "superstorePay": "N",
            "showType": "chessboardType", "curPage": str(page),
            "priceS": "0", "priceE": "9999999", "searchType": "1",
            "reduceKeyword": "", "isFuzzy": "0",
            "rtnCateDatainfo": {
                "cateCode": "", "cateLv": "-1", "keyword": keyword,
                "curPage": str(page), "historyDoPush": "false",
                "timestamp": int(time.time() * 1000),
            },
            "flag": 2018, "serviceCode": "MT01", "addressSearchData": {},
            "adSource": "tenmax",
        },
    }


@st.cache_data(ttl=600, show_spinner=False)
def fetch_momo_page(keyword: str, page: int) -> list:
    resp = requests.post(
        MOMO_API, headers=HEADERS, json=build_momo_payload(keyword, page), timeout=20
    )
    resp.raise_for_status()
    return resp.json().get("rtnSearchData", {}).get("goodsInfoList", []) or []


def crawl_gifts(keyword: str, pages: int, platforms: list, delay: float):
    rows, warns = [], []
    total = max(1, pages * len(platforms))
    done = 0
    bar = st.progress(0.0, text="開始搜尋禮物...")

    if "PChome" in platforms:
        for i in range(1, pages + 1):
            bar.progress(min(done / total, 1.0), text=f"PChome：第 {i} / {pages} 頁...")
            done += 1
            try:
                data = fetch_pchome_page(keyword, i)
            except Exception as e:
                warns.append(f"PChome 第 {i} 頁失敗：{e}")
                break
            prods = data.get("prods") or []
            if not prods:
                break
            for p in prods:
                rows.append({
                    "平台": "PChome", "品名": p.get("name", ""), "價格": p.get("price"),
                    "連結": f"https://24h.pchome.com.tw/prod/{p.get('Id', '')}",
                })
            tp = data.get("totalPage")
            if tp and i >= int(tp):
                break
            if i < pages and delay > 0:
                time.sleep(delay)

    if "momo" in platforms:
        for i in range(1, pages + 1):
            bar.progress(min(done / total, 1.0), text=f"momo：第 {i} / {pages} 頁...")
            done += 1
            try:
                goods = fetch_momo_page(keyword, i)
            except Exception as e:
                warns.append(f"momo 第 {i} 頁失敗：{e}")
                break
            if not goods:
                break
            for g in goods:
                rows.append({
                    "平台": "momo", "品名": g.get("goodsName", ""), "價格": g.get("goodsPrice", ""),
                    "連結": "https://www.momoshop.com.tw/goods/GoodsDetail.jsp?i_code="
                    + str(g.get("goodsCode", "")),
                })
            if i < pages and delay > 0:
                time.sleep(delay)

    bar.progress(1.0, text="搜尋完成")
    bar.empty()
    return pd.DataFrame(rows), warns


def clean_gifts(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["價格"] = pd.to_numeric(
        df["價格"].astype(str).str.replace(r"[^\d]", "", regex=True), errors="coerce"
    )
    df = df.dropna(subset=["品名", "價格"])
    df = df[df["價格"] > 0].drop_duplicates(subset=["平台", "品名", "價格"])
    df["價格"] = df["價格"].astype(int)
    return df.reset_index(drop=True)


# ------------------------------------------------------------------
# 表白卡片
# ------------------------------------------------------------------
CARD_CSS = """
<style>
.love-card{max-width:640px;margin:0 auto;padding:32px 36px;border-radius:24px;
  background:linear-gradient(135deg,#fff5f7 0%,#ffe3ec 100%);
  border:2px solid #ffc2d4;box-shadow:0 12px 32px rgba(255,105,150,.25);
  color:#4a2c3a;font-family:"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;}
.love-card .to{font-size:1.5rem;font-weight:700;color:#d6336c;margin-bottom:12px;}
.love-card .msg{font-size:1.1rem;line-height:1.9;white-space:normal;}
.love-card .gift{margin-top:20px;padding:14px 16px;border-radius:14px;background:#fff;
  border:1px dashed #ff8fab;font-size:.98rem;}
.love-card .gift a{color:#d6336c;font-weight:600;text-decoration:none;}
.love-card .heart{text-align:center;font-size:2rem;margin-bottom:6px;}
</style>
"""


def safe_link(url: str) -> str:
    return url if isinstance(url, str) and url.startswith(ALLOWED_LINK_PREFIX) else ""


def render_card(frm: str, to: str, msg: str, gift: str = "", gift_url: str = "", price: str = ""):
    to_e = html.escape(to or "你")
    msg_e = html.escape(msg or "").replace("\n", "<br>")
    gift_html = ""
    if gift:
        label = html.escape(gift)
        link = safe_link(gift_url)
        price_txt = f"（約 NT$ {html.escape(price)}）" if price else ""
        name_html = f'<a href="{html.escape(link)}" target="_blank" rel="noopener">{label}</a>' if link else label
        gift_html = f'<div class="gift">🎁 我為你準備了一份小禮物：{name_html} {price_txt}</div>'
    st.markdown(
        CARD_CSS
        + f'<div class="love-card"><div class="heart">💌</div>'
        f'<div class="to">致 {to_e}</div><div class="msg">{msg_e}</div>{gift_html}</div>',
        unsafe_allow_html=True,
    )


# ------------------------------------------------------------------
# 收件人頁面（網址帶有 ?mode=confess ...）
# ------------------------------------------------------------------
def recipient_view(p) -> None:
    frm = p.get("frm", "")[:20]
    to = p.get("to", "")[:20]
    msg = p.get("msg", "")[:400]
    gift = p.get("gift", "")[:80]
    gift_url = p.get("url", "")[:300]
    price = re.sub(r"[^\d]", "", p.get("price", ""))[:7]

    st.markdown(
        "<style>.stApp{background:linear-gradient(180deg,#fff0f5 0%,#ffe0ea 100%);}</style>",
        unsafe_allow_html=True,
    )
    render_card(frm, to, msg, gift, gift_url, price)

    st.markdown(
        f"<h3 style='text-align:center;margin-top:28px;color:#d6336c'>"
        f"💖 {html.escape(frm or '我')} 想問你：願意和我在一起嗎？</h3>",
        unsafe_allow_html=True,
    )

    ss = st.session_state
    ss.setdefault("no_count", 0)
    ss.setdefault("yes", False)
    ss.setdefault("declined", False)
    ss.setdefault("celebrated", False)

    def say_yes():
        ss["yes"], ss["declined"] = True, False

    def say_no():
        if ss["no_count"] >= len(NO_LABELS) - 1:
            ss["declined"], ss["yes"] = True, False
        else:
            ss["no_count"] += 1

    _, c1, c2, _ = st.columns([1, 2, 2, 1])
    c1.button("我願意 💖", type="primary", width="stretch", on_click=say_yes)
    c2.button(NO_LABELS[min(ss["no_count"], len(NO_LABELS) - 1)], width="stretch", on_click=say_no)

    if ss["yes"]:
        if not ss["celebrated"]:
            st.balloons()
            st.snow()
            ss["celebrated"] = True
        st.success(f"🎉 太好了！請把這個畫面截圖傳給 {frm or '對方'}，讓他知道你的答案吧！")
    elif ss["declined"]:
        st.info(
            f"謝謝你認真看完，也謝謝你誠實回答 🙏 "
            f"{frm or '對方'}會尊重你的決定，也很高興能認識你。"
        )
    elif NO_REPLIES[min(ss["no_count"], len(NO_REPLIES) - 1)]:
        st.caption(NO_REPLIES[min(ss["no_count"], len(NO_REPLIES) - 1)])


# 收件人模式：直接顯示並結束
if st.query_params.get("mode") == "confess":
    recipient_view(st.query_params)
    st.stop()

# ------------------------------------------------------------------
# 製作者頁面
# ------------------------------------------------------------------
st.title("💌 表白禮物比價系統")
st.caption("挑一份划算的禮物、寫下真心話，再產生專屬連結送給對方。")

ss = st.session_state
ss.setdefault("gifts", None)
ss.setdefault("gift", None)
ss.setdefault("msg", "")

with st.sidebar:
    st.header("使用步驟")
    st.markdown("1. 填寫基本資料\n2. 搜尋禮物並比價\n3. 撰寫表白文字\n4. 預覽並取得連結")
    st.divider()
    base_url = st.text_input(
        "你的 App 網址（選填）",
        placeholder="https://xxx.streamlit.app",
        help="部署後把網址貼在這裡，就能產生完整的分享連結。",
    )
    st.caption("💡 表白是分享心意，也請尊重對方的答案。")

tab_info, tab_gift, tab_msg, tab_share = st.tabs(
    ["① 基本資料", "② 禮物比價", "③ 表白文字", "④ 預覽 / 分享"]
)

# ---------------------------- ① 基本資料 ----------------------------
with tab_info:
    c1, c2 = st.columns(2)
    c1.text_input("你的名字（暱稱）", key="frm", max_chars=20)
    c2.text_input("對方的名字（暱稱）", key="to", max_chars=20)
    st.number_input("禮物預算 (NT$)", min_value=100, max_value=100000, value=1000, step=100, key="budget")
    st.info("填完後到「② 禮物比價」搜尋禮物。")

frm = ss.get("frm", "").strip()
to = ss.get("to", "").strip()
budget = int(ss.get("budget", 1000))

# ---------------------------- ② 禮物比價 ----------------------------
with tab_gift:
    with st.form("gift_form"):
        g1, g2 = st.columns([2, 2])
        preset = g1.selectbox("禮物類型", GIFT_PRESETS)
        custom = g2.text_input("自訂關鍵字（選「自訂…」時使用）")
        g3, g4, g5 = st.columns(3)
        pages = g3.number_input("爬取頁數（每個平台）", 1, 5, 1)
        platforms = g4.multiselect("比價平台", PLATFORMS, default=PLATFORMS)
        delay = g5.slider("每頁間隔秒數", 0.0, 5.0, 1.0, 0.5)
        go = st.form_submit_button("🔍 搜尋並比價", width="stretch")

    if go:
        kw = custom.strip() if preset == "自訂…" else preset
        if not kw:
            st.warning("請輸入關鍵字")
        elif not platforms:
            st.warning("請至少選一個平台")
        else:
            raw, warns = crawl_gifts(kw, int(pages), platforms, delay)
            for w in warns:
                st.warning(w)
            df_new = clean_gifts(raw) if not raw.empty else pd.DataFrame()
            if df_new.empty:
                ss["gifts"] = None
                st.error("查無資料，請換個關鍵字或稍後再試。")
            else:
                ss["gifts"] = {"df": df_new, "kw": kw}
                ss["gift"] = None

    data = ss.get("gifts")
    if not data:
        st.info("按下「搜尋並比價」開始。")
    else:
        gdf: pd.DataFrame = data["df"]
        st.subheader(f"「{data['kw']}」比價結果")

        only_budget = st.checkbox(f"只顯示預算內（≤ NT$ {budget:,}）", value=True)
        view = gdf[gdf["價格"] <= budget] if only_budget else gdf
        if view.empty:
            st.warning("預算內沒有符合的商品，可以調高預算或取消勾選。")
        else:
            present = [p for p in PLATFORMS if p in view["平台"].unique()]
            cols = st.columns(len(present))
            for col, p in zip(cols, present):
                s = view[view["平台"] == p]["價格"]
                col.metric(f"{p}｜中位數", f"{s.median():,.0f}", f"最低 {s.min():,.0f}", delta_color="off")
            if len(present) == 2:
                med = view.groupby("平台")["價格"].median()
                lo, hi = med.idxmin(), med.idxmax()
                if med[lo] != med[hi]:
                    st.success(f"💡 這類禮物在 **{lo}** 的價格中位數較低（{med[lo]:,.0f} vs {med[hi]:,.0f}）。")

            fig = px.box(
                view, x="平台", y="價格", color="平台", color_discrete_map=COLORS,
                points="all", hover_data=["品名"], title="禮物價格分布",
            )
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig)

            st.markdown("**挑選禮物**")
            order = st.radio(
                "排序方式",
                ["最便宜優先", "最接近預算（預算內挑質感）"],
                horizontal=True,
            )
            ranked = (
                view.sort_values("價格")
                if order == "最便宜優先"
                else view.assign(_d=(budget - view["價格"]).abs()).sort_values("_d")
            ).head(40).reset_index(drop=True)

            labels = [f"{r['平台']}｜NT$ {r['價格']:,}｜{r['品名'][:50]}" for _, r in ranked.iterrows()]
            idx = st.selectbox("選擇要附上的禮物", range(len(ranked)), format_func=lambda i: labels[i])
            chosen = ranked.iloc[idx]
            st.markdown(f"[🔗 查看商品頁面]({chosen['連結']})")
            if st.button("🎁 就選這個！", type="primary"):
                ss["gift"] = {
                    "name": chosen["品名"][:80],
                    "url": chosen["連結"],
                    "price": int(chosen["價格"]),
                    "platform": chosen["平台"],
                }
                st.success("已加入表白卡片！")

    if ss.get("gift"):
        g = ss["gift"]
        st.info(f"目前選擇：{g['platform']}｜NT$ {g['price']:,}｜{g['name']}")
        if st.button("移除禮物"):
            ss["gift"] = None
            st.rerun()

# ---------------------------- ③ 表白文字 ----------------------------
def apply_template():
    tone = ss["tone"]
    i = ss["tpl_idx"]
    ss["msg"] = TEMPLATES[tone][i].format(to=ss.get("to", "").strip() or "你", frm=ss.get("frm", "").strip() or "我")


with tab_msg:
    t1, t2 = st.columns(2)
    t1.selectbox("風格", list(TEMPLATES.keys()), key="tone")
    t2.radio("範本", [0, 1], format_func=lambda i: f"範本 {i + 1}", horizontal=True, key="tpl_idx")
    st.button("✨ 套用範本", on_click=apply_template)
    st.text_area("表白內容（可自由修改）", key="msg", height=260, max_chars=400)

# ---------------------------- ④ 預覽 / 分享 ----------------------------
with tab_share:
    msg = ss.get("msg", "").strip()
    if not msg:
        st.info("請先到「③ 表白文字」套用範本或自行撰寫內容。")
    else:
        g = ss.get("gift") or {}
        st.markdown("**卡片預覽**")
        render_card(frm, to, msg, g.get("name", ""), g.get("url", ""), str(g.get("price", "")))

        params = {"mode": "confess", "frm": frm, "to": to, "msg": msg}
        if g:
            params.update({"gift": g["name"], "url": g["url"], "price": str(g["price"])})
        query = "?" + urlencode(params)
        full = (base_url.strip().rstrip("/") + "/" + query) if base_url.strip() else query

        st.markdown("**專屬表白連結**")
        if not base_url.strip():
            st.caption("尚未填寫 App 網址，下方是網址後面要接的參數；部署後請在左側填入網址即可得到完整連結。")
        st.code(full, language=None)
        if len(full) > 1800:
            st.warning("連結偏長，部分通訊軟體可能會截斷，建議縮短表白內容或禮物名稱。")

        st.download_button(
            "⬇️ 下載表白文字 (.txt)",
            data=msg.encode("utf-8"),
            file_name="confession.txt",
            mime="text/plain",
        )
        st.caption("對方打開連結後會看到這張卡片，並可以回答你的問題；答案不會被記錄，請對方截圖回覆你。")
