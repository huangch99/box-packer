import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import random
import copy

# --- PAGE CONFIG ---
st.set_page_config(page_title="Smart 3D Packer", layout="wide")
st.title("📦 Smart 3D Packing (Bounding Box Optimization)")

# --- SIDEBAR ---
st.sidebar.header("1. Container Size")
bin_w = st.sidebar.number_input("Width", value=50, step=1)
bin_h = st.sidebar.number_input("Height", value=50, step=1)
bin_d = st.sidebar.number_input("Depth", value=50, step=1)

st.sidebar.header("2. Optimization")
enable_optimization = st.sidebar.checkbox("🚀 AI Auto-Optimize", value=True, help="Shuffles items to find the tightest bounding box.")
iterations = st.sidebar.slider("Attempts", 10, 100, 30) if enable_optimization else 1

st.sidebar.header("3. Items")
default_items = """Laptop, 30, 2, 20
ShoeBox, 20, 10, 30
Cube, 15, 15, 15
Tube, 5, 5, 45
BigBox, 25, 25, 25"""
items_text = st.sidebar.text_area("List (Name, W, H, D)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- LOGIC: BOUNDING BOX ---
def get_bounding_box_stats(bin_obj):
    """
    Calculates the tightest box that surrounds all packed items.
    Logic based on user request: finding max extent in x, y, z.
    """
    if not bin_obj.items:
        return 0, (0,0,0)

    max_x = 0
    max_y = 0
    max_z = 0
    
    for item in bin_obj.items:
        # py3dbp updates .width, .height, .depth to the ROTATED dimensions after packing
        # .position is [x, y, z] (float)
        
        pos_x, pos_y, pos_z = float(item.position[0]), float(item.position[1]), float(item.position[2])
        dim_w, dim_h, dim_d = float(item.width), float(item.height), float(item.depth)
        
        # Calculate extent
        if pos_x + dim_w > max_x: max_x = pos_x + dim_w
        if pos_y + dim_h > max_y: max_y = pos_y + dim_h
        if pos_z + dim_d > max_z: max_z = pos_z + dim_d
        
    used_volume = max_x * max_y * max_z
    return used_volume, (max_x, max_y, max_z)

# --- VISUALIZATION FUNCTION ---
def get_cube_mesh(size, position, color, opacity=1.0, name="", wireframe=False):
    dx, dy, dz = size
    x, y, z = position
    
    # Vertices
    x_coords = [x, x+dx, x+dx, x,    x, x+dx, x+dx, x]
    y_coords = [y, y,    y+dy, y+dy, y, y,    y+dy, y+dy]
    z_coords = [z, z,    z,    z,    z+dz, z+dz, z+dz, z+dz]

    if wireframe:
        # Draw lines for wireframe (Bounding Box)
        # Lines connecting bottom face, top face, and connecting pillars
        lines_x = [x, x+dx, x+dx, x, x,  x, x+dx, x+dx, x, x,  x, x, x+dx, x+dx, x+dx, x+dx]
        lines_y = [y, y, y+dy, y+dy, y,  y, y, y+dy, y+dy, y,  y, y, y, y, y+dy, y+dy]
        lines_z = [z, z, z, z, z,        z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz]
        # Note: A simple mesh scatter is easier for wireframes in plotly
        return go.Scatter3d(
            x=[x, x+dx, x+dx, x, x, x, x+dx, x+dx, x, x, x+dx, x+dx, x, x, x, x],
            y=[y, y, y+dy, y+dy, y, y, y, y, y+dy, y+dy, y+dy, y+dy, y+dy, y, y, y],
            z=[z, z, z, z, z, z+dz, z+dz, z+dz, z+dz, z, z, z+dz, z+dz, z+dz, z, z+dz],
            mode='lines',
            line=dict(color=color, width=4),
            name=name, hoverinfo='name'
        )

    # Solid Cube
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    
    return go.Mesh3d(
        x=x_coords, y=y_coords, z=z_coords,
        i=i, j=j, k=k,
        color=color, opacity=opacity, name=name,
        showscale=False, hoverinfo='name'
    )

# --- MAIN LOGIC ---
if run_btn:
    # 1. Parse Input
    raw_items = []
    try:
        lines = items_text.strip().split('\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 4:
                name = parts[0].strip()
                w = float(parts[1].strip())
                h = float(parts[2].strip())
                d = float(parts[3].strip())
                raw_items.append(Item(name, w, h, d, 1))
    except Exception as e:
        st.error(f"Formatting Error: {e}")
        st.stop()

    if not raw_items:
        st.stop()

    # 2. Setup Simulation
    box_dims = (bin_w, bin_h, bin_d)
    
    # Best Result Variables
    best_bin = None
    best_item_count = -1
    min_bounding_vol = float('inf') # We want to MINIMIZE this
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    strategies = range(iterations) if enable_optimization else range(1)
    
    # 3. Loop
    for i in strategies:
        if enable_optimization:
            status_text.text(f"Optimizing layout {i+1}/{iterations}...")
            progress_bar.progress((i+1)/iterations)
        
        # Setup Packer
        packer = Packer()
        packer.add_bin(Bin('MainBin', bin_w, bin_h, bin_d, 99999))
        
        # Shuffle items for this attempt (except first run)
        current_items = copy.deepcopy(raw_items)
        if i > 0:
            random.shuffle(current_items)
        
        for item in current_items:
            packer.add_item(item)
        
        packer.pack()
        result_bin = packer.bins[0]
        
        # --- SCORING LOGIC ---
        count = len(result_bin.items)
        bb_vol, bb_dims = get_bounding_box_stats(result_bin)
        
        # Logic: 
        # 1. Strictly prefer packing MORE items.
        # 2. If count is equal, prefer SMALLER bounding box volume (tighter pack).
        
        if count > best_item_count:
            best_item_count = count
            min_bounding_vol = bb_vol
            best_bin = result_bin
        elif count == best_item_count:
            if bb_vol < min_bounding_vol:
                min_bounding_vol = bb_vol
                best_bin = result_bin

    progress_bar.empty()
    status_text.empty()

    # 4. Display Results
    if best_bin:
        b = best_bin
        bb_vol, bb_dims = get_bounding_box_stats(b)
        
        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Items Packed", f"{len(b.items)} / {len(raw_items)}")
        c2.metric("Used Dimensions (W,H,D)", f"{bb_dims[0]:.1f}, {bb_dims[1]:.1f}, {bb_dims[2]:.1f}")
        c3.metric("Density Score", f"{iterations} tries")

        # Warning for unfitted
        if len(b.unfitted_items) > 0:
            st.warning(f"⚠️ Could not fit: " + ", ".join([i.name for i in b.unfitted_items]))
        else:
            st.success("✅ All items fit!")

        # 5. 3D Visualization
        fig = go.Figure()
        
        # A. Draw Container (Grey)
        fig.add_trace(get_cube_mesh([bin_w, bin_h, bin_d], (0,0,0), 'grey', 0.05, 'Max Container'))
        
        # B. Draw Bounding Box (Red Wireframe) - Shows the "Used Space"
        fig.add_trace(get_cube_mesh(bb_dims, (0,0,0), 'red', 1.0, 'Bounding Box', wireframe=True))
        
        # C. Draw Items
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3']
        for idx, item in enumerate(b.items):
            dims = [float(item.width), float(item.height), float(item.depth)]
            pos = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
            fig.add_trace(get_cube_mesh(dims, pos, colors[idx % len(colors)], 1.0, item.name))

        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[0, bin_w], title='W'),
                yaxis=dict(range=[0, bin_h], title='H'),
                zaxis=dict(range=[0, bin_d], title='D'),
                aspectmode='data'
            ),
            height=600,
            margin=dict(l=0, r=0, b=0, t=0),
            title=f"Best Layout: {bb_dims[0]:.1f}x{bb_dims[1]:.1f}x{bb_dims[2]:.1f} (Red Box = Used Space)"
        )
        st.plotly_chart(fig, use_container_width=True)
