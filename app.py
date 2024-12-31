import streamlit as st
import requests
import networkx as nx
import plotly.graph_objects as go
import pandas as pd
import plotly.express as px
from datetime import datetime

# 스타일 적용
st.markdown(
    """
    <style>
    body {
        background-color: #ffffff;  /* 배경 색상 흰색으로 설정 */
        color: #333333;
    }
    .reportview-container .main .block-container {
        padding: 2rem 1rem 2rem 1rem;
    }
    div[role="radiogroup"] label {
        color: #333333;
    }
    h2, h1 {
        color: #000000;
        text-align: center;
        font-size: 24px;
        font-weight: bold;
    }
    label {
        font-size: 16px;
        color: #333333;
    }
    .stSlider {
        color: #333333;
    }
    .stButton button {
        background-color: #000000;
        color: #ffffff;
        font-weight: bold;
        padding: 0.5rem 2rem;
        border-radius: 5px;
    }
    .stButton button:hover {
        background-color: #333333;
    }
    .wallet-overview {
        background-color: #f0f0f0; 
        color: #333333; 
        padding: 20px; 
        border-radius: 10px;
    }
    .stat-box {
        background-color: #f0f0f0;
        color: #333333;
        padding: 15px;
        border-radius: 10px;
        margin-top: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

def get_transaction_history(address):
    try:
        url = f"https://blockchain.info/rawaddr/{address}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"데이터를 가져오는 중 오류 발생: {e}")
        return None

def visualize_address_connections(address, transactions, filter_type=None, min_amount=None, time_range=None):
    G = nx.DiGraph()

    for tx in transactions['txs']:
        tx_time = pd.to_datetime(tx['time'], unit='s')
        if time_range and (tx_time < time_range[0] or tx_time > time_range[1]):
            continue
        if filter_type == 'Sent' and tx['result'] > 0:
            continue
        if filter_type == 'Received' and tx['result'] < 0:
            continue
        for out in tx['out']:
            if 'addr' in out and (min_amount is None or out['value'] >= min_amount):
                G.add_edge(tx['hash'], out['addr'], value=out['value'], timestamp=tx_time)

    pos = nx.spring_layout(G)
    edge_trace = []
    for edge in G.edges(data=True):
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_trace.append(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            hoverinfo='none',
            mode='lines'))

    node_trace = go.Scatter(
        x=[], y=[], text=[], mode='markers+text', textposition="top center", hoverinfo='text',
        marker=dict(showscale=True, colorscale='YlGnBu', size=[], color=[], 
                    colorbar=dict(thickness=15, title='Transaction Amount', xanchor='left', titleside='right')))

    for node in G.nodes():
        x, y = pos[node]
        node_trace['x'] += tuple([x])
        node_trace['y'] += tuple([y])
        node_info = f"Address: {node}, Transactions: {len(G[node])}"
        node_trace['text'] += tuple([node_info])
        node_trace['marker']['size'] += tuple([20 + len(G[node]) * 5])
        node_trace['marker']['color'] += tuple([len(G[node])])

    fig = go.Figure(data=edge_trace + [node_trace], layout=go.Layout(
        title='Transaction Graph',
        showlegend=False,
        hovermode='closest',
        margin=dict(b=20, l=5, r=5, t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    ))
    return fig

def get_wallet_overview(transactions):
    total_received = sum(tx['result'] for tx in transactions['txs'] if tx['result'] > 0)
    total_sent = sum(-tx['result'] for tx in transactions['txs'] if tx['result'] < 0)
    balance = transactions['final_balance']
    first_transaction = pd.to_datetime(min(tx['time'] for tx in transactions['txs']), unit='s')
    last_transaction = pd.to_datetime(max(tx['time'] for tx in transactions['txs']), unit='s')

    last_24h_time = pd.Timestamp.now() - pd.Timedelta(hours=24)
    last_24h_received = sum(tx['result'] for tx in transactions['txs'] if tx['result'] > 0 and pd.to_datetime(tx['time'], unit='s') >= last_24h_time)
    last_24h_sent = sum(-tx['result'] for tx in transactions['txs'] if tx['result'] < 0 and pd.to_datetime(tx['time'], unit='s') >= last_24h_time)

    return {
        'balance': balance,
        'total_received': total_received,
        'total_sent': total_sent,
        'first_transaction': first_transaction,
        'last_transaction': last_transaction,
        'last_24h_received': last_24h_received,
        'last_24h_sent': last_24h_sent
    }

def display_wallet_overview(overview):
    overview_html = f"""
    <div class='wallet-overview'>
        <h2 style='color: #000000; text-align: center;'>지갑 개요</h2>
        <p><strong>잔액:</strong> {overview['balance']} 사토시</p>
        <p><strong>받은 총액:</strong> {overview['total_received']} 사토시</p>
        <p><strong>보낸 총액:</strong> {overview['total_sent']} 사토시</p>
        <p><strong>최초 트랜잭션 날짜:</strong> {overview['first_transaction']}</p>
        <p><strong>마지막 트랜잭션 날짜:</strong> {overview['last_transaction']}</p>
        <p><strong>최근 24시간 받은 금액:</strong> {overview['last_24h_received']} 사토시</p>
        <p><strong>최근 24시간 보낸 금액:</strong> {overview['last_24h_sent']} 사토시</p>
    </div>
    """
    st.markdown(overview_html, unsafe_allow_html=True)

# 트랜잭션 세부 정보 표시
def display_transaction_details(transactions):
    st.subheader("트랜잭션 세부 정보")
    for tx in transactions['txs']:
        with st.expander(f"트랜잭션 {tx['hash']}"):
            st.write(f"날짜: {pd.to_datetime(tx['time'], unit='s')}")
            st.write(f"결과: {'받은 금액' if tx['result'] > 0 else '보낸 금액'}: {abs(tx['result'])} 사토시")
            st.write(f"수수료: {tx['fee']} 사토시")
            st.write("입력 주소:")
            for inp in tx['inputs']:
                st.write(f"- {inp['prev_out']['addr'] if 'addr' in inp['prev_out'] else '알 수 없음'}")
            st.write("출력 주소:")
            for out in tx['out']:
                st.write(f"- {out['addr'] if 'addr' in out else '알 수 없음'}")

# 추가 통계 정보 제공
def get_additional_stats(transactions):
    total_fees = sum(tx['fee'] for tx in transactions['txs'] if 'fee' in tx)
    avg_fee = total_fees / len(transactions['txs'])
    avg_sent = sum(-tx['result'] for tx in transactions['txs'] if tx['result'] < 0) / len(transactions['txs'])
    avg_received = sum(tx['result'] for tx in transactions['txs'] if tx['result'] > 0) / len(transactions['txs'])

    return {
        'avg_fee': avg_fee,
        'avg_sent': avg_sent,
        'avg_received': avg_received
    }

# 추가 통계 정보 및 그래프 표시
def display_additional_stats_and_graph(stats):
    st.markdown(
        """
        <div class='stat-box'>
            <h2>추가 통계 정보</h2>
            <p><strong>평균 수수료:</strong> {avg_fee:.2f} 사토시</p>
            <p><strong>평균 보낸 금액:</strong> {avg_sent:.2f} 사토시</p>
            <p><strong>평균 받은 금액:</strong> {avg_received:.2f} 사토시</p>
        </div>
        """.format(
            avg_fee=stats['avg_fee'],
            avg_sent=stats['avg_sent'],
            avg_received=stats['avg_received']
        ), 
        unsafe_allow_html=True
    )

    # 평균 보낸 금액과 받은 금액 시각화
    data = {
        '금액 종류': ['평균 보낸 금액', '평균 받은 금액'],
        '사토시': [stats['avg_sent'], stats['avg_received']]
    }
    df = pd.DataFrame(data)
    fig = px.bar(df, x='금액 종류', y='사토시', title="평균 보낸 금액 vs 평균 받은 금액", text='사토시')
    st.plotly_chart(fig)

def main():
    st.markdown("<div style='text-align: center; font-size: 24px; color: #333333;'><b>BLOCK-DARK</b></div>", unsafe_allow_html=True)

    # 사이드바로 UI 구성
    st.sidebar.header("조사 설정")

    address = st.sidebar.text_input("비트코인 주소 입력:")
    trace_depth = st.sidebar.slider("자동 추적 깊이", 1, 5, 2)
    
    start_date = st.sidebar.date_input("시작 날짜")
    end_date = st.sidebar.date_input("종료 날짜")
    
    min_amount = st.sidebar.number_input("최소 트랜잭션 금액 (사토시):", min_value=0, value=0)
    filter_type = st.sidebar.selectbox("트랜잭션 필터:", ['전체', '보낸 트랜잭션', '받은 트랜잭션'])

    # 테스트 모드 확인
    if address == "test":
        address = "1PuJjnF476W3zXfVYmJfGnouzFDAXakkL4"
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2024, 10, 23)

    time_range = (pd.Timestamp(start_date), pd.Timestamp(end_date))

    if st.sidebar.button("조사 시작"):
        if address:
            transactions = get_transaction_history(address)
            if transactions:
                overview = get_wallet_overview(transactions)
                display_wallet_overview(overview)

                # 추가 통계 정보 계산 및 표시
                stats = get_additional_stats(transactions)
                display_additional_stats_and_graph(stats)

                st.header("트랜잭션 그래프")
                fig = visualize_address_connections(address, transactions, filter_type, min_amount, time_range)
                st.plotly_chart(fig)

                # 트랜잭션 세부 정보 표시
                display_transaction_details(transactions)

if __name__ == "__main__":
    main()
