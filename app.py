import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="Sequential 3D Packer", layout="wide")
st.title("📦 Sequential 3D Packer (Lock First 2 Items)")
st.markdown("""
**Logic:**
1. **Phase 1:** Solves the best layout for the **First 2 Items** (e.g. placing them side-by-side).
2. **Phase 2:** **LOCKS** that layout.
3. **Phase 3:** Attempts to fit the remaining items into the gaps without moving the first two.
""")

# --- SIDEBAR ---
st.sidebar.header("1. Container (Fixed)")
cont_l = st.sidebar.number_input("Length (X)", value=8.25, step=0.01, format="%.2f")
cont_w = st.sidebar.number_input("Width (Y)", value=6.38, step=0.01, format="%.2f")
cont_h = st.sidebar.number_input("Height (Z)", value=3.75, step=0.01, format="%.2f")

st.sidebar.header("2. Items")
# Note: The order in this list determines who is "First 2"
default_items = """MEC102A, 7, 3.7, 2.92
MSC137A, 3.6, 3.35, 3.55
MAC105A, 4, 2.8, 0.8"""
items_text = st.sidebar.text_area("List (Name, L, W, H)", value=default_items, height=200, help="The top 2 items will be locked.")
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- VISUALIZATION HELPER ---
def get_cube_trace(size, position, color, name="", is_wireframe=False):
    dx, dy, dz = size
    x, y, z = position
    if is_wireframe:
        x_lines = [x, x+dx, x+dx, x, x,    x, x+dx, x+dx, x, x,    x, x, x+dx, x+dx, x+dx, x+dx]
        y_lines = [y, y, y+dy, y+dy, y,    y, y, y+dy, y+dy, y,    y, y, y, y, y+dy, y+dy]
        z_lines = [z, z, z, z, z,          z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz]
        return go.Scatter3d(x=x_lines, y=y_lines, z=z_lines, mode='lines', line=dict(color='black', width=5), name=name, hoverinfo='name')
    else:
        x_corners = [x, x+dx, x+dx, x,    x, x+dx, x+dx, x]
        y_corners = [y, y,    y+dy, y+dy, y, y,    y+dy, y+dy]
        z_corners = [z, z,    z,    z,    z+dz, z+dz, z+dz, z+dz]
        i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        hover_text = f"<b>{name}</b><br>Size: {dx:.3f}x{dy:.3f}x{dz:.3f}<br>Pos: {x:.2f}, {y:.2f}, {z:.2f}"
        return go.Mesh3d(x=x_corners, y=y_corners, z=z_corners, i=i, j=j, k=k, color=color, opacity=1.0, name=name, text=name, hovertemplate=hover_text, showscale=False)

# --- MAIN LOGIC ---
if run_btn:
    TOLERANCE = 0.001 
    raw_items_data = []
    try:
        lines = items_text.strip().split('\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 4:
                name = parts[0].strip()
                l = float(parts[1].strip()) - TOLERANCE
                w = float(parts[2].strip()) - TOLERANCE
                h = float(parts[3].strip()) - TOLERANCE
                raw_items_data.append({'name': name, 'l': l, 'w': w, 'h': h})
    except Exception as e: st.error(f"Error: {e}"); st.stop()
    
    if len(raw_items_data) < 2:
        st.error("Need at least 2 items to use 'Locking' logic.")
        st.stop()

    # --- SPLIT ITEMS ---
    # Group A: The First 2 Items (To be locked)
    # Group B: The Rest (To be fitted in gaps)
    items_to_lock = raw_items_data[:2]
    items_to_fit  = raw_items_data[2:]

    st.info(f"🔒 **Phase 1:** Locking position for **{items_to_lock[0]['name']}** and **{items_to_lock[1]['name']}**...")

    # --- PHASE 1: OPTIMIZE THE LOCKED GROUP ---
    # We search for the best configuration (Mode + Order) for just the first 2 items.
    
    sim_modes = [
        {'name': 'Standard', 'dims': [cont_l, cont_w, cont_h], 'map': 'LWH'},
        {'name': 'Width-Saver', 'dims': [cont_l, cont_h, cont_w], 'map': 'LHW'}
    ]
    
    permutations = list(itertools.permutations(items_to_lock))
    
    locked_config = None # Will store: {'mode': mode_obj, 'order': item_list}
    
    # Find ANY configuration that fits the first 2 items successfully
    # Prefer "Width-Saver" if both work, as it tends to stack side-by-side
    found_fit = False
    
    for mode in sim_modes:
        sim_dims = mode['dims']
        for order in permutations:
            packer = Packer()
            packer.add_bin(Bin('LockBin', sim_dims[0], sim_dims[1], sim_dims[2], 9999))
            for d in order:
                packer.add_item(Item(d['name'], d['l'], d['w'], d['h'], 1))
            
            packer.pack()
            b = packer.bins[0]
            
            if len(b.items) == 2: # Both fitted!
                locked_config = {'mode': mode, 'order': order}
                found_fit = True
                # We break here? Or keep searching? 
                # For this puzzle, we take the first valid fit for the base.
                break 
        if found_fit: break
    
    if not found_fit:
        st.error("❌ Critical Failure: Even the first 2 items could not fit together.")
        st.stop()
        
    st.success(f"✅ Phase 1 Complete. Locked Logic: **{locked_config['mode']['name']}**.")

    # --- PHASE 2: ADD THE REST ---
    # Now we re-run the packer with the LOCKED settings.
    # 1. Use the Locked Mode (Standard or Width-Saver)
    # 2. Add Locked Items FIRST (in the specific order found in Phase 1)
    # 3. Add Remaining items AFTER
    
    st.info("🚀 **Phase 2:** Attempting to fit remaining items into gaps...")
    
    final_mode = locked_config['mode']
    final_sim_dims = final_mode['dims']
    
    # The packing list starts with the locked items in their fixed order
    final_packing_list = list(locked_config['order']) + items_to_fit
    
    # Note: We can optionally try to permute 'items_to_fit', but we MUST NOT touch the start of the list.
    # Let's just try to pack them simply first.
    
    packer = Packer()
    packer.add_bin(Bin('FinalBin', final_sim_dims[0], final_sim_dims[1], final_sim_dims[2], 9999))
    
    for d in final_packing_list:
        packer.add_item(Item(d['name'], d['l'], d['w'], d['h'], 1))
        
    packer.pack()
    b = packer.bins[0]

    # --- RESULTS MAPPING ---
    visual_items = []
    for item in b.items:
        d = [float(item.width), float(item.height), float(item.depth)]
        p = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
        
        if final_mode['map'] == 'LHW':
            # Map Back: SimY->RealZ, SimZ->RealY
            real_d = [d[0], d[2], d[1]]
            real_p = [p[0], p[2], p[1]]
        else:
            real_d = d
            real_p = p
            
        visual_items.append({'name': item.name, 'dim': real_d, 'pos': real_p})

    # --- METRICS & DISPLAY ---
    count = len(visual_items)
    c1, c2 = st.columns(2)
    c1.metric("Total Packed", f"{count} / {len(raw_items_data)}")
    
    if count == len(raw_items_data):
        st.success("✅ **Perfect Fit!** The 3rd item fit into the gap left by the first two.")
    else:
        st.warning(f"⚠️ Only {count} items fit. The locked configuration might be too tight.")
        if b.unfitted_items:
            st.write("Unfitted: " + ", ".join([i.name for i in b.unfitted_items]))

    # 3D Plot
    fig = go.Figure()
    fig.add_trace(get_cube_trace([cont_l, cont_w, cont_h], (0,0,0), 'black', "Container", True))
    
    colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA']
    for i, dat in enumerate(visual_items):
        # Add tolerance back
        d = [dat['dim'][0]+TOLERANCE, dat['dim'][1]+TOLERANCE, dat['dim'][2]+TOLERANCE]
        fig.add_trace(get_cube_trace(d, dat['pos'], colors[i%4], dat['name']))

    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[0, cont_l], title='Length (X)'),
            yaxis=dict(range=[0, cont_w], title='Width (Y)'),
            zaxis=dict(range=[0, cont_h], title='Height (Z)'),
            aspectmode='manual', aspectratio=dict(x=cont_l, y=cont_w, z=cont_h)
        ),
        height=700, margin=dict(l=0,r=0,b=0,t=0),
        title=f"Sequential Result ({count} Items)"
    )
    st.plotly_chart(fig, use_container_width=True)
