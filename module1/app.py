import os
from typing import List, Dict
import streamlit as st
from dotenv import load_dotenv

# ==========================================
# 1. 環境變數 (.env) 管理
# ==========================================
load_dotenv()
APP_ENV: str = os.getenv("APP_ENV", "development")


# ==========================================
# 2. OOP 核心：基礎類別與繼承 (AWS, Azure, GCP)
# ==========================================
class CloudVM:
    """雲端虛擬機器父類別"""
    provider_name: str = "通用雲端"

    def __init__(self, instance_id: str, monthly_cost: float, cpu_utilization: float) -> None:
        self.instance_id: str = instance_id
        self.monthly_cost: float = monthly_cost
        self.cpu_utilization: float = cpu_utilization

    def is_idle(self) -> bool:
        """判定是否為閒置主機 (CPU < 15%)"""
        return self.cpu_utilization < 15.0

    def calculate_savings(self) -> float:
        """預估省額（由子類別覆寫）"""
        return 0.0


class AWSVM(CloudVM):
    """AWS 雲端主機"""
    provider_name: str = "AWS"

    def calculate_savings(self) -> float:
        # AWS 閒置主機：建議規格降級，預估可省 50% 費用
        if self.is_idle():
            return self.monthly_cost * 0.5
        return 0.0


class AzureVM(CloudVM):
    """Azure 雲端主機"""
    provider_name: str = "Azure"

    def calculate_savings(self) -> float:
        # Azure 閒置主機：建議轉用保留折扣，預估可省 40% 費用
        if self.is_idle():
            return self.monthly_cost * 0.4
        return 0.0


class GCPVM(CloudVM):
    """GCP 雲端主機"""
    provider_name: str = "GCP"

    def calculate_savings(self) -> float:
        # GCP 閒置主機：建議轉用 Spot VM，預估可省 60% 費用
        if self.is_idle():
            return self.monthly_cost * 0.6
        return 0.0


# ==========================================
# 3. 資源管理器 (用 List 容器維護物件狀態)
# ==========================================
class SimpleFinOpsManager:
    """維護多雲主機清單與核心商業邏輯"""
    def __init__(self) -> None:
        self.vms: List[CloudVM] = []

    def add_vm(self, vm: CloudVM) -> bool:
        """新增主機 (防禦性編程：檢查重複 ID)"""
        for item in self.vms:
            if item.instance_id == vm.instance_id:
                raise ValueError(f"主機 ID `{vm.instance_id}` 已存在！")
        self.vms.append(vm)
        return True

    def delete_vm(self, instance_id: str) -> bool:
        """刪除主機"""
        self.vms = [vm for vm in self.vms if vm.instance_id != instance_id]
        return True

    def filter_vms(self, provider_name: str) -> List[CloudVM]:
        """依雲端平台名稱過濾"""
        if provider_name == "全部":
            return self.vms
        return [vm for vm in self.vms if vm.provider_name == provider_name]


# ==========================================
# 4. Streamlit 互動介面
# ==========================================
st.set_page_config(page_title="初學者 FinOps 雲端成本管理系統", layout="wide")

st.title("☁️ 雲端 FinOps 簡單成本優化系統")
st.caption(f"目前運行環境：`{APP_ENV}` | 適合 Python 模組一專案實作")

# 初始化 Session State 保持資料狀態
if "manager" not in st.session_state:
    manager = SimpleFinOpsManager()
    # 預設載入 3 台不同平台的範例主機
    manager.add_vm(AWSVM("i-aws-01", 200.0, 8.0))    # AWS (閒置)
    manager.add_vm(AzureVM("vm-az-02", 300.0, 85.0))  # Azure (正常)
    manager.add_vm(GCPVM("gce-gcp-03", 150.0, 10.0))  # GCP (閒置)
    st.session_state.manager = manager

manager: SimpleFinOpsManager = st.session_state.manager

# 介面分頁
tab_view, tab_add, tab_delete = st.tabs(["📊 檢視與分析", "➕ 新增主機", "🗑️ 刪除主機"])

# ------------------------------------------
# 分頁 1：檢視與條件過濾
# ------------------------------------------
with tab_view:
    st.subheader("🔍 雲端主機清單與優化評估")
    
    selected_provider = st.selectbox("選擇雲端平台過濾", ["全部", "AWS", "Azure", "GCP"])
    filtered_list = manager.filter_vms(selected_provider)

    # 計算統計指標
    total_cost = sum(vm.monthly_cost for vm in filtered_list)
    total_savings = sum(vm.calculate_savings() for vm in filtered_list)

    col1, col2, col3 = st.columns(3)
    col1.metric("主機數量", f"{len(filtered_list)} 台")
    col2.metric("每月維運總成本", f"${total_cost:,.1f}")
    col3.metric("預估可省金額", f"${total_savings:,.1f}")

    st.divider()

    # 展示表格
    if filtered_list:
        table_data = []
        for vm in filtered_list:
            table_data.append({
                "雲端平台": vm.provider_name,  # 直接讀取屬性，不會受 Streamlit 熱重載影響
                "主機 ID": vm.instance_id,
                "月租費 ($)": f"${vm.monthly_cost:.1f}",
                "CPU 利用率 (%)": f"{vm.cpu_utilization}%",
                "狀態評估": "⚠️ 閒置主機" if vm.is_idle() else "✅ 負載正常",
                "建議可省金額": f"${vm.calculate_savings():.1f}"
            })
        st.dataframe(table_data, use_container_width=True)
    else:
        st.info("尚無符合條件的主機資料。")


# ------------------------------------------
# 分頁 2：新增主機
# ------------------------------------------
with tab_add:
    st.subheader("➕ 輸入資料並建立雲端物件")
    
    with st.form("add_form", clear_on_submit=True):
        provider = st.selectbox("請選擇雲端平台", ["AWS", "Azure", "GCP"])
        vm_id = st.text_input("主機 ID (例如: i-web-01)", placeholder="請輸入唯一 ID")
        cost = st.number_input("每月預算費用 ($)", min_value=1.0, value=100.0, step=10.0)
        cpu = st.number_input("平均 CPU 利用率 (%)", min_value=0.0, max_value=100.0, value=10.0)

        submitted = st.form_submit_button("新增主機")

        if submitted:
            if not vm_id:
                st.error("❌ 新增失敗：主機 ID 不能為空白！")
            else:
                try:
                    # 多型建立對應的 OOP 物件
                    if provider == "AWS":
                        new_vm = AWSVM(vm_id, cost, cpu)
                    elif provider == "Azure":
                        new_vm = AzureVM(vm_id, cost, cpu)
                    else:
                        new_vm = GCPVM(vm_id, cost, cpu)

                    manager.add_vm(new_vm)
                    st.success(f"✅ 成功新增 {provider} 主機：`{vm_id}`！")
                    st.rerun()
                except ValueError as err:
                    st.error(f"❌ 新增失敗（防禦機制）：{err}")


# ------------------------------------------
# 分頁 3：刪除主機
# ------------------------------------------
with tab_delete:
    st.subheader("🗑️ 選擇主機進行退役刪除")
    
    if not manager.vms:
        st.warning("目前清單中沒有任何主機。")
    else:
        # 建立選項清單
        options = [vm.instance_id for vm in manager.vms]
        target_id = st.selectbox("請選擇欲刪除的主機 ID：", options)

        if st.button("確認刪除", type="primary"):
            manager.delete_vm(target_id)
            st.success(f"✅ 已成功刪除主機：`{target_id}`")
            st.rerun()