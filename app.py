import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import decimal
import copy # Needed to copy lists for multiple simulations

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Multi-Item Box Visualizer", layout="wide")
st.title("📦 Multi-Item Shipping Calculator (Smart Mode)")
st.markdown("""
**Logic:** This tool now runs **3 Simulations** (Volume, Length, Area) and automatically displays the best result.
""")

# --- SESSION STATE INITIALIZATION ---
if 'items_to_pack' not in st.session_state:
    st.session_state.items_to_pack = []

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("1. Define Box (Inner Dims)")
box_l = st.sidebar.number_input("Box Length", min_value=0.1, value=12.0)
box_w = st.sidebar.number_input("Box Width", min_value=0.1, value=12.0)
box_h = st.sidebar.number_input("Box Height", min_value=0.1, value=12.0)
st.sidebar.caption("Weight capacity is disabled (Calculates by Size only)")

st.sidebar.markdown("---")
st.sidebar.header("2. Add Items")
item_name = st.sidebar.text_input("Item Name", value="Product A")

c1, c2, c3 = st.sidebar.columns(3)
i_l = c1.number_input("L", min_value=0.1, value=5.0)
i_w = c2.number_input("W", min_value=0.1, value=5.0)
i_h = c3.number_input("H", min_value=0.1, value=5.0)

i_qty = st.sidebar.number_input("Qty", value=1, min_value=1)
i_color = st.sidebar.color_picker("Color", "#00CC96")

if st.sidebar.button("Add Item to List"):
    for _ in range(int(i_qty)):
        st.session_state.items_to_pack.append({
            "name": item_name,
            "l": i_l, 
            "w": i_w, 
            "h": i_h,
            "color": i_color
        })
    st.success(f"Added {i_qty} x {item_name}")

if st.sidebar.button("Clear Entire List"):
    st.session_state.items_to_pack = []

# --- MAIN PANEL: ITEM LIST ---
st.subheader(f"Current Item List ({len(st.session_state.items_to_pack)} items)")

if len(st.session_state.items_to_pack) > 0:
    # Header Row
    c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2.5, 2, 1, 0.5, 0.5])
    c1.markdown("**No.**")
    c2.markdown("**Name**")
    c3.markdown("**Dims (LxWxH)**")
    c4.markdown("**Color**")
    c5.markdown("**Swap**")
    c6.markdown("**Del**")
    
    st.markdown("---")

    # Loop through items
    for i, item in enumerate(st.session_state.items_to_pack):
        c1, c2, c3, c4, c5, c6 = st.columns([0.5, 2.5, 2, 1, 0.5, 0.5])
        
        with c1: st.write(f"#{i+1}")
        with c2: st.write(item['name'])
        with c3: st.write(f"{item['l']} x {item['w']} x {item['h']}")
        with c4: st.color_picker("", item['color'], disabled=True, label_visibility="collapsed", key=f"col_{i}")
        
        with c5:
            if st.button("🔄", key=f"swap_list_{i}", help="Swap Width and Height"):
                st.session_state.items_to_pack[i]['w'], st.session_state.items_to_pack[i]['h'] = \
                st.session_state.items_to_pack[i]['h'], st.session_state.items_to_pack[i]['w']
                st.rerun()
        
        with c6:
            if st.button("🗑️", key=f"remove_{i}", help="Remove this item"):
                st.session_state.items_to_pack.pop(i)
                st.rerun()
else:
    st.info("Add items from the sidebar to start.")

# --- VISUALIZATION FUNCTIONS ---
def get_cube_trace(x, y, z, l, w, h, color, name, opacity=1.0):
    x_pts = [x, x+l, x+l, x, x, x+l, x+l, x]
    y_pts = [y, y, y+w, y+w, y, y, y+w, y+w]
    z_pts = [z, z, z, z, z+h, z+h, z+h, z+h]

    return go.Mesh3d(
        x=x_pts, y=y_pts, z=z_pts,
        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
        opacity=opacity,
        color=color,
        name=name,
        showscale=False,
        hoverinfo='name'
    )

def get_wireframe(l, w, h):
    pts = [
        (0,0,0), (l,0,0), (l,w,0), (0,w,0), (0,0,0),
        (0,0,h), (l,0,h), (l,w,h), (0,w,h), (0,0,h),
        (0,0,h), (0,0,0), (l,0,0), (l,0,h),
        (l,w,h), (l,w,0), (0,w,0), (0,w,h)
    ]
    X = [p[0] for p in pts]
    Y = [p[1] for p in pts]
    Z = [p[2] for p in pts]
    return go.Scatter3d(x=X, y=Y, z=Z, mode='lines', line=dict(color='black', width=4), name='Bin Frame')

def analyze_failure(bin_obj, item_obj):
    bin_dims = sorted([float(bin_obj.width), float(bin_obj.height), float(bin_obj.depth)])
    item_dims = sorted([float(item_obj.width), float(item_obj.height), float(item_obj.depth)])
    
    if any(i > b for i, b in zip(item_dims, bin_dims)):
        return "❌ Item is too large for box (Dimensions mismatch)"
    return "📦 Not enough remaining space (or fragmentation)"

# --- CORE PACKING ALGORITHM WRAPPER ---
def run_packing_simulation(items, sort_key_func):
    """
    Runs a single packing simulation with a specific sorting strategy.
    Returns: (packer_object, unfitted_count, packed_volume)
    """
    # 1. Sort items based on the provided key function (Strategy)
    sorted_items = sorted(items, key=sort_key_func, reverse=True)
    
    # 2. Setup Packer
    packer = Packer()
    packer.add_bin(Bin('MainBox', box_l, box_w, box_h, 999999999)) # Infinite weight
    
    # 3. Add Items
    for i, item in enumerate(sorted_items):
        p_item = Item(f"{item['name']}-{i}", item['l'], item['w'], item['h'], 1)
        p_item.color = item['color']
        packer.add_item(p_item)
        
    # 4. Run
    packer.pack()
    box = packer.bins[0]
    
    # 5. Calculate stats to decide if this is the "Winner"
    unfitted_count = len(box.unfitted_items)
    
    packed_volume = 0.0
    for item in box.items:
        packed_volume += float(item.width) * float(item.height) * float(item.depth)
        
    return packer, unfitted_count, packed_volume

# --- CALCULATION LOGIC ---
if st.button("Calculate Packing (Auto-Optimize)", type="primary"):
    if not st.session_state.items_to_pack:
        st.warning("Please add items first.")
    else:
        # --- RUN 3 PARALLEL STRATEGIES ---
        
        # Strategy A: Volume (L*W*H) - Standard
        pack_A, fail_A, vol_A = run_packing_simulation(
            st.session_state.items_to_pack, 
            lambda x: x['l'] * x['w'] * x['h']
        )
        
        # Strategy B: Longest Side (max(L,W,H)) - Good for pipes/long items
        pack_B, fail_B, vol_B = run_packing_simulation(
            st.session_state.items_to_pack, 
            lambda x: max(x['l'], x['w'], x['h'])
        )
        
        # Strategy C: Widest Footprint (L*W) - Good for flat items
        pack_C, fail_C, vol_C = run_packing_simulation(
            st.session_state.items_to_pack, 
            lambda x: x['l'] * x['w']
        )

        # --- COMPARE RESULTS ---
        # We prefer fewer failures. If failures are equal, we prefer higher packed volume.
        # List format: (Packer, FailCount, Volume, Name)
        results = [
            (pack_A, fail_A, vol_A, "Volume Sort"),
            (pack_B, fail_B, vol_B, "Longest-Side Sort"),
            (pack_C, fail_C, vol_C, "Area Sort")
        ]
        
        # Sort results: Primary key = FailCount (ascending), Secondary key = Volume (descending)
        results.sort(key=lambda x: (x[1], -x[2]))
        
        # THE WINNER
        winner_packer, winner_fail, winner_vol, winner_name = results[0]
        winner_box = winner_packer.bins[0]
        
        # --- DISPLAY RESULTS ---
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.subheader("Optimization Result")
            st.success(f"🏆 Best Strategy: **{winner_name}**")
            
            total_box_volume = box_l * box_w * box_h
            efficiency = (winner_vol / total_box_volume) * 100
            
            st.metric("Packed Items", len(winner_box.items))
            st.metric("Volume Utilization", f"{efficiency:.1f}%")
            st.caption(f"Used: {winner_vol:.2f} / Total: {total_box_volume:.2f}")

            if len(winner_box.unfitted_items) == 0:
                st.success("✅ All items fit!")
            else:
                st.error(f"❌ {len(winner_box.unfitted_items)} items did NOT fit.")
                
                for item in winner_box.unfitted_items:
                    reason = analyze_failure(winner_box, item)
                    with st.expander(f"{item.name} (Failed)", expanded=True):
                        st.write(f"**Reason:** {reason}")
                        st.caption(f"Dims: {float(item.width)}x{float(item.height)}x{float(item.depth)}")

        with col2:
            max_x_draw = box_l
            fig = go.Figure()
            
            # Draw Wireframe
            fig.add_trace(get_wireframe(box_l, box_w, box_h))
            
            # Draw Packed Items
            for item in winner_box.items:
                x, y, z = float(item.position[0]), float(item.position[1]), float(item.position[2])
                w, h, d = float(item.get_dimension()[0]), float(item.get_dimension()[1]), float(item.get_dimension()[2])
                color = getattr(item, 'color', 'gray')
                fig.add_trace(get_cube_trace(x, y, z, w, h, d, color, item.name))

            # Draw Unfitted Items
            if len(winner_box.unfitted_items) > 0:
                gap = box_l * 0.1
                start_x = box_l + gap
                current_z = 0
                
                for item in winner_box.unfitted_items:
                    w, h, d = float(item.width), float(item.height), float(item.depth)
                    color = getattr(item, 'color', 'red')
                    fig.add_trace(get_cube_trace(start_x, 0, current_z, w, h, d, color, f"FAILED: {item.name}", opacity=0.5))
                    
                    current_z += d
                    if (start_x + w) > max_x_draw:
                        max_x_draw = start_x + w

                fig.add_trace(go.Scatter3d(
                    x=[start_x], y=[0], z=[current_z + 1],
                    mode='text', text=['Did Not Fit'],
                    textfont=dict(color='red', size=12)
                ))

            layout = go.Layout(
                scene=dict(
                    xaxis=dict(title='Length (x)', range=[0, max_x_draw * 1.1]),
                    yaxis=dict(title='Width (y)', range=[0, max(box_w, box_l)]),
                    zaxis=dict(title='Height (z)', range=[0, max(box_h, box_l)]),
                    aspectmode='data'
                ),
                margin=dict(l=0, r=0, b=0, t=0),
                height=600
            )
            
            fig.update_layout(layout)
            st.plotly_chart(fig, use_container_width=True)
