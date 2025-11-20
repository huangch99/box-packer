import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="Solver 3D Packer", layout="wide")
st.title("📦 3D Packer (Permutation Solver)")
st.markdown("""
This solver tries **every possible order** of items to force them into the box.
It keeps the Container dimensions **fixed** (No container rotation).
""")

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Container Dimensions (Fixed)")
# We map Length -> X, Width -> Y, Height -> Z
cont_l = st.sidebar.number_input("Length (X axis)", value=8.25, step=0.01, format="%.2f")
cont_w = st.sidebar.number_input("Width (Y axis)", value=6.38, step=0.01, format="%.2f")
cont_h = st.sidebar.number_input("Height (Z axis)", value=3.75, step=0.01, format="%.2f")

st.sidebar.header("2. Items")
# The tricky puzzle list
default_items = """MEC102A, 7, 3.7, 2.92
MSC137A, 3.6, 3.35, 3.55
MAC105A, 4, 2.8, 0.8"""
items_text = st.sidebar.text_area("List (Name, L, W, H)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- VISUALIZATION HELPER ---
def get_cube_trace(size, position, color, name="", is_wireframe=False, opacity=1.0):
    dx, dy, dz = size
    x, y, z = position
    
    if is_wireframe:
        # Draw solid lines for the container outline (Black Wireframe)
        # Sequence to draw a cube in one continuous line (mostly)
        x_lines = [x, x+dx, x+dx, x, x,    x, x+dx, x+dx, x, x,    x, x, x+dx, x+dx, x+dx, x+dx]
        y_lines = [y, y, y+dy, y+dy, y,    y, y, y+dy, y+dy, y,    y, y, y, y, y+dy, y+dy]
        z_lines = [z, z, z, z, z,          z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz]
        
        return go.Scatter3d(
            x=x_lines, y=y_lines, z=z_lines,
            mode='lines',
            line=dict(color='black', width=5),
            name=name, hoverinfo='name'
        )
    
    else:
        # Draw colored mesh for items
        x_corners = [x, x+dx, x+dx, x,    x, x+dx, x+dx, x]
        y_corners = [y, y,    y+dy, y+dy, y, y,    y+dy, y+dy]
        z_corners = [z, z,    z,    z,    z+dz, z+dz, z+dz, z+dz]
        
        i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        
        hover_text = f"<b>{name}</b><br>Size: {dx:.2f} x {dy:.2f} x {dz:.2f}<br>Pos: {x:.2f}, {y:.2f}, {z:.2f}"
        
        return go.Mesh3d(
            x=x_corners, y=y_corners, z=z_corners,
            i=i, j=j, k=k,
            color=color, opacity=opacity, 
            name=name, text=name, hovertemplate=hover_text, showscale=False
        )

# --- MAIN LOGIC ---
if run_btn:
    # 1. INPUT PARSING (With Tolerance)
    # Subtract 0.005 to prevent floating point math errors (3.75 vs 3.7500001)
    TOLERANCE = 0.005 
    raw_items = []
    try:
        lines = items_text.strip().split('\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 4:
                name = parts[0].strip()
                l = float(parts[1].strip()) - TOLERANCE
                w = float(parts[2].strip()) - TOLERANCE
                h = float(parts[3].strip()) - TOLERANCE
                raw_items.append(Item(name, l, w, h, 1))
    except Exception as e:
        st.error(f"Input Error: {e}"); st.stop()
    
    if not raw_items: st.stop()

    # 2. PERMUTATION SOLVER
    # Generate ALL possible orderings of the items.
    # e.g. [A, B, C], [A, C, B], [B, A, C] ...
    all_orders = list(itertools.permutations(raw_items))
    
    best_bin = None
    best_count = -1
    winning_order = []
    
    progress_bar = st.progress(0)
    
    # Loop through every order until we find one that fits everything
    for i, item_order in enumerate(all_orders):
        progress_bar.progress((i + 1) / len(all_orders))
        
        packer = Packer()
        # Fixed Container (User Input)
        packer.add_bin(Bin('MainBin', cont_l, cont_w, cont_h, 99999))
        
        for item in item_order:
            packer.add_item(item)
        
        packer.pack()
        b = packer.bins[0]
        
        # Check results
        if len(b.items) > best_count:
            best_count = len(b.items)
            best_bin = b
            
        # Optimization: If we packed everything, STOP immediately.
        if len(b.items) == len(raw_items):
            winning_order = [item.name for item in item_order]
            break
            
    progress_bar.empty()

    # 3. DISPLAY METRICS
    if best_bin:
        b = best_bin
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Items Packed", f"{len(b.items)} / {len(raw_items)}")
        
        if len(b.items) == len(raw_items):
            st.success(f"✅ **Success!** Solution found using order: {' → '.join(winning_order)}")
        else:
            st.error(f"❌ Could not fit all items. Best attempt: {len(b.items)} items.")
            if len(b.unfitted_items) > 0:
                st.write("Unfitted: " + ", ".join([i.name for i in b.unfitted_items]))

        # 4. TRUE-SCALE VISUALIZATION
        fig = go.Figure()
        
        # Draw Container (Black Wireframe)
        fig.add_trace(get_cube_trace([cont_l, cont_w, cont_h], (0,0,0), 'black', name="Container", is_wireframe=True))
        
        # Draw Items
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A']
        for idx, item in enumerate(b.items):
            # Add tolerance back for visual accuracy
            dims = [float(item.width)+TOLERANCE, float(item.height)+TOLERANCE, float(item.depth)+TOLERANCE]
            pos = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
            
            fig.add_trace(get_cube_trace(dims, pos, colors[idx % len(colors)], name=item.name, opacity=1.0))

        # Force 1:1 Aspect Ratio
        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[0, cont_l], title='Length (X)'),
                yaxis=dict(range=[0, cont_w], title='Width (Y)'),
                zaxis=dict(range=[0, cont_h], title='Height (Z)'),
                aspectmode='manual',
                aspectratio=dict(x=cont_l, y=cont_w, z=cont_h)
            ),
            height=700, margin=dict(l=0, r=0, b=0, t=0),
            title=f"Result ({len(b.items)} items packed)"
        )
        st.plotly_chart(fig, use_container_width=True)
