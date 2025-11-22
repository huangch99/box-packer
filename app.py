import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import random
import copy

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Multi-Item Box Visualizer", layout="wide")
st.title("📦 Multi-Item Shipping Calculator")
st.markdown("**Logic:** Use 'Smart Optimization' to try 100s of combinations and find the best fit.")

# --- SESSION STATE INITIALIZATION ---
if 'items_to_pack' not in st.session_state:
    st.session_state.items_to_pack = []
if 'status_msg' not in st.session_state:
    st.session_state.status_msg = ""
if 'status_type' not in st.session_state:
    st.session_state.status_type = ""

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("1. Define Box (Inner Dims)")
box_l = st.sidebar.number_input("Box Length", min_value=0.1, value=12.0)
box_w = st.sidebar.number_input("Box Width", min_value=0.1, value=12.0)
box_h = st.sidebar.number_input("Box Height", min_value=0.1, value=12.0)

st.sidebar.markdown("---")
st.sidebar.header("2. Packing Algorithm")
use_smart_packing = st.sidebar.checkbox("🚀 Enable Smart Optimization", value=True, help="Runs 50 simulations with random variations to find the best packing layout.")

st.sidebar.markdown("---")
st.sidebar.header("3. Add Items")
item_name = st.sidebar.text_input("Item Name", value="Product A")
c1, c2, c3 = st.sidebar.columns(3)
i_l = c1.number_input("L", min_value=0.1, value=5.0)
i_w = c2.number_input("W", min_value=0.1, value=5.0)
i_h = c3.number_input("H", min_value=0.1, value=5.0)
i_qty = st.sidebar.number_input("Qty", value=1, min_value=1)
i_color = st.sidebar.color_picker("Color", "#00CC96")

# --- ADD ITEM ---
if st.sidebar.button("Add Item to List"):
    for _ in range(int(i_qty)):
        st.session_state.items_to_pack.append({
            "name": item_name,
            "l": i_l, "w": i_w, "h": i_h, "color": i_color
        })
    st.session_state.status_msg = f"✅ Successfully added {i_qty} x {item_name}"
    st.session_state.status_type = "success"
    st.rerun()

# --- CLEAR LIST ---
if st.sidebar.button("Clear Entire List"):
    st.session_state.items_to_pack = []
    st.session_state.status_msg = "🧹 List cleared"
    st.session_state.status_type = "info"
    st.rerun()

# --- MAIN PANEL: LIST & NOTIFICATIONS ---
st.subheader(f"Current Item List ({len(st.session_state.items_to_pack)} items)")

if st.session_state.status_msg:
    if st.session_state.status_type == "success": st.success(st.session_state.status_msg)
    elif st.session_state.status_type == "error": st.error(st.session_state.status_msg)
    else: st.info(st.session_state.status_msg)
    st.session_state.status_msg = "" # Clear after showing

if len(st.session_state.items_to_pack) > 0:
    c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2.5, 2, 1, 0.5, 0.5])
    c1.markdown("**No.**"); c2.markdown("**Name**"); c3.markdown("**Dims**"); c4.markdown("**Color**"); c5.markdown("**Swap**"); c6.markdown("**Del**")
    st.markdown("---")
    for i, item in enumerate(st.session_state.items_to_pack):
        c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2.5, 2, 1, 0.5, 0.5])
        with c1: st.write(f"#{i+1}")
        with c2: st.write(item['name'])
        with c3: st.write(f"{item['l']} x {item['w']} x {item['h']}")
        with c4: st.color_picker("", item['color'], disabled=True, label_visibility="collapsed", key=f"col_{i}")
        with c5:
            if st.button("🔄", key=f"swap_{i}"):
                st.session_state.items_to_pack[i]['w'], st.session_state.items_to_pack[i]['h'] = st.session_state.items_to_pack[i]['h'], st.session_state.items_to_pack[i]['w']
                st.session_state.status_msg = f"🔄 Swapped {item['name']}"; st.session_state.status_type = "info"; st.rerun()
        with c6:
            if st.button("🗑️", key=f"del_{i}"):
                n = st.session_state.items_to_pack[i]['name']
                st.session_state.items_to_pack.pop(i)
                st.session_state.status_msg = f"❌ Removed {n}"; st.session_state.status_type = "error"; st.rerun()

# --- VISUALIZATION HELPERS ---
def get_cube_trace(x, y, z, l, w, h, color, name, opacity=1.0):
    x_pts = [x, x+l, x+l, x, x, x+l, x+l, x]; y_pts = [y, y, y+w, y+w, y, y, y+w, y+w]; z_pts = [z, z, z, z, z+h, z+h, z+h, z+h]
    return go.Mesh3d(x=x_pts, y=y_pts, z=z_pts, i=[7,0,0,0,4,4,6,6,4,0,3,2], j=[3,4,1,2,5,6,5,2,0,1,6,3], k=[0,7,2,3,6,7,1,1,5,5,7,6], opacity=opacity, color=color, name=name, showscale=False, hoverinfo='name')

def get_wireframe(l, w, h):
    pts = [(0,0,0), (l,0,0), (l,w,0), (0,w,0), (0,0,0), (0,0,h), (l,0,h), (l,w,h), (0,w,h), (0,0,h), (0,0,h), (0,0,0), (l,0,0), (l,0,h), (l,w,h), (l,w,0), (0,w,0), (0,w,h)]
    return go.Scatter3d(x=[p[0] for p in pts], y=[p[1] for p in pts], z=[p[2] for p in pts], mode='lines', line=dict(color='black', width=4), name='Bin Frame')

# --- NEW ALGORITHM: SMART OPTIMIZATION ---
def pack_with_optimization(items, b_l, b_w, b_h, iterations=50):
    """
    Runs the packing algorithm multiple times with random shuffles 
    and keeps the best result.
    """
    best_packer = None
    best_volume = -1
    best_item_count = -1
    
    # 1. Strategy A: Largest First (Baseline)
    strategies = [sorted(items, key=lambda x: x['l']*x['w']*x['h'], reverse=True)]
    
    # 2. Strategy B: Random Shuffles (Monte Carlo)
    if iterations > 0:
        for _ in range(iterations):
            shuffled = copy.deepcopy(items)
            random.shuffle(shuffled)
            strategies.append(shuffled)
            
    # Run Simulations
    for item_list in strategies:
        packer = Packer()
        packer.add_bin(Bin('MainBox', b_l, b_w, b_h, 999999999))
        for i, item in enumerate(item_list):
            p_item = Item(f"{item['name']}-{i}", item['l'], item['w'], item['h'], 1)
            p_item.color = item['color']
            packer.add_item(p_item)
        
        packer.pack()
        
        # Score this attempt
        box = packer.bins[0]
        current_vol = sum([float(i.width)*float(i.height)*float(i.depth) for i in box.items])
        current_count = len(box.items)
        
        # If this is the best so far, save it
        if current_count > best_item_count:
            best_packer = packer
            best_item_count = current_count
            best_volume = current_vol
        elif current_count == best_item_count and current_vol > best_volume:
            best_packer = packer
            best_volume = current_vol

    return best_packer

# --- CALCULATE BUTTON ---
if st.button("Calculate Packing", type="primary"):
    if not st.session_state.items_to_pack:
        st.warning("Add items first.")
    else:
        iterations = 50 if use_smart_packing else 0
        
        # Run the Smart Packer
        with st.spinner(f"Running {iterations+1} packing simulations..."):
            packer = pack_with_optimization(st.session_state.items_to_pack, box_l, box_w, box_h, iterations)
            
        box = packer.bins[0]
        
        # --- DISPLAY RESULTS ---
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.subheader("Results")
            if use_smart_packing:
                st.caption("✅ Optimization Complete")
                
            packed_vol = sum([float(i.width)*float(i.height)*float(i.depth) for i in box.items])
            total_vol = box_l * box_w * box_h
            efficiency = (packed_vol / total_vol) * 100
            
            st.metric("Packed Items", len(box.items))
            st.metric("Volume Utilization", f"{efficiency:.1f}%")
            st.caption(f"Used: {packed_vol:.2f} / Total: {total_box_volume:.2f}") # Total box volume variable fixed

            if len(box.unfitted_items) == 0:
                st.success("✅ All items fit!")
            else:
                st.error(f"❌ {len(box.unfitted_items)} items did NOT fit.")
                for item in box.unfitted_items:
                    with st.expander(f"{item.name} (Failed)"):
                        st.write("Reason: Not enough remaining space")
                        st.caption(f"Dims: {float(item.width)}x{float(item.height)}x{float(item.depth)}")

        with col2:
            fig = go.Figure()
            fig.add_trace(get_wireframe(box_l, box_w, box_h))
            
            max_x = box_l
            for item in box.items:
                x,y,z = float(item.position[0]), float(item.position[1]), float(item.position[2])
                w,h,d = float(item.get_dimension()[0]), float(item.get_dimension()[1]), float(item.get_dimension()[2])
                fig.add_trace(get_cube_trace(x,y,z,w,h,d, getattr(item, 'color', 'gray'), item.name))
            
            if len(box.unfitted_items) > 0:
                start_x = box_l + (box_l * 0.1)
                cz = 0
                for item in box.unfitted_items:
                    w,h,d = float(item.width), float(item.height), float(item.depth)
                    fig.add_trace(get_cube_trace(start_x, 0, cz, w, h, d, getattr(item, 'color', 'red'), f"FAILED: {item.name}", 0.5))
                    cz += d
                    if start_x + w > max_x: max_x = start_x + w
                fig.add_trace(go.Scatter3d(x=[start_x], y=[0], z=[cz+1], mode='text', text=['Did Not Fit'], textfont=dict(color='red')))

            fig.update_layout(scene=dict(xaxis=dict(range=[0, max_x*1.1]), yaxis=dict(range=[0, max(box_w, box_l)]), zaxis=dict(range=[0, max(box_h, box_l)]), aspectmode='data'), margin=dict(l=0,r=0,b=0,t=0), height=600)
            st.plotly_chart(fig, use_container_width=True)
