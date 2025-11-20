import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import random
import copy
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="Smart 3D Packer", layout="wide")
st.title("📦 Smart 3D Packing (Floor-Fill + Auto-Rotation)")

# --- SIDEBAR ---
st.sidebar.header("1. Container Size")
bin_w = st.sidebar.number_input("Width", value=8.25, step=0.01, format="%.2f")
bin_h = st.sidebar.number_input("Height", value=6.38, step=0.01, format="%.2f")
bin_d = st.sidebar.number_input("Depth", value=3.75, step=0.01, format="%.2f")

st.sidebar.header("2. Optimization")
enable_optimization = st.sidebar.checkbox("🚀 AI Auto-Optimize", value=True, help="Runs multiple strategies (Floor Filling, etc) and rotates the box.")
iterations = st.sidebar.slider("Attempts per Strategy", 5, 30, 10) if enable_optimization else 1

st.sidebar.header("3. Items")
# Defaulting to your specific puzzle case
default_items = """MSC137A, 3.6, 3.55, 3.35
MEC102A, 7, 3.7, 2.92
MAC105A, 4, 2.8, 0.8"""
items_text = st.sidebar.text_area("List (Name, W, H, D)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- HELPER: BOUNDING BOX CALCULATION ---
def get_bounding_box_stats(bin_obj):
    """Calculates the tightest box that surrounds all packed items."""
    if not bin_obj.items:
        return 0, (0,0,0)

    max_x, max_y, max_z = 0, 0, 0
    
    for item in bin_obj.items:
        # Dimensions and positions are floats
        dim_w, dim_h, dim_d = float(item.width), float(item.height), float(item.depth)
        pos_x, pos_y, pos_z = float(item.position[0]), float(item.position[1]), float(item.position[2])
        
        if pos_x + dim_w > max_x: max_x = pos_x + dim_w
        if pos_y + dim_h > max_y: max_y = pos_y + dim_h
        if pos_z + dim_d > max_z: max_z = pos_z + dim_d
        
    used_volume = max_x * max_y * max_z
    return used_volume, (max_x, max_y, max_z)

# --- HELPER: 3D MESH GENERATION ---
def get_cube_mesh(size, position, color, opacity=1.0, name="", wireframe=False):
    dx, dy, dz = size
    x, y, z = position
    
    if wireframe:
        # Draws the outline of a box
        return go.Scatter3d(
            x=[x, x+dx, x+dx, x, x,  x, x+dx, x+dx, x, x,  x, x, x+dx, x+dx, x+dx, x+dx],
            y=[y, y, y+dy, y+dy, y,  y, y, y+dy, y+dy, y,  y, y, y, y, y+dy, y+dy],
            z=[z, z, z, z, z,        z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz],
            mode='lines',
            line=dict(color=color, width=5),
            name=name, hoverinfo='name'
        )

    # Draws a solid box
    x_coords = [x, x+dx, x+dx, x,    x, x+dx, x+dx, x]
    y_coords = [y, y,    y+dy, y+dy, y, y,    y+dy, y+dy]
    z_coords = [z, z,    z,    z,    z+dz, z+dz, z+dz, z+dz]
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    
    return go.Mesh3d(
        x=x_coords, y=y_coords, z=z_coords,
        i=i, j=j, k=k,
        color=color, opacity=opacity, name=name,
        showscale=False, hoverinfo='name'
    )

# --- MAIN EXECUTION ---
if run_btn:
    # 1. Parse Inputs
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

    # 2. Setup Optimization Variables
    original_dims = [bin_w, bin_h, bin_d]
    # Generate all 6 rotations of the container (e.g. 8x6x3, 3x8x6...)
    box_orientations = list(set(itertools.permutations(original_dims)))
    
    best_bin = None
    best_item_count = -1
    min_bounding_vol = float('inf') 
    
    # Progress Bar Setup
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # We define 4 strategies. 
    # If optimization is off, we only run Strategy 0 once.
    strategies_count = iterations if enable_optimization else 1
    
    # 3. The Loop
    for i in range(strategies_count):
        current_items_base = copy.deepcopy(raw_items)
        
        # --- STRATEGY SELECTOR ---
        # Strategy 0: FLOOR FILLING (Sort by Area: W*D) - Best for side-by-side
        # Strategy 1: TALL ITEMS FIRST (Sort by Height) - Best for vertical stacking
        # Strategy 2: BIG ITEMS FIRST (Sort by Volume) - Best for reducing gaps
        # Strategy 3+: RANDOM - Brute force
        
        if i == 0:
            current_items_base.sort(key=lambda x: float(x.width)*float(x.depth), reverse=True)
            strategy_name = "Floor Filling (Area)"
        elif i == 1:
            current_items_base.sort(key=lambda x: float(x.height), reverse=True)
            strategy_name = "Height Stacking"
        elif i == 2:
            current_items_base.sort(key=lambda x: float(x.width)*float(x.height)*float(x.depth), reverse=True)
            strategy_name = "Volume Filling"
        else:
            random.shuffle(current_items_base)
            strategy_name = "Random Shuffle"
            
        # Inner Loop: Test every Box Orientation for this strategy
        total_variations = len(box_orientations)
        for idx, box_dim in enumerate(box_orientations):
            
            # UI Feedback
            if idx % 2 == 0:
                status_text.text(f"Strategy: {strategy_name} | Box: {box_dim}")
            
            packer = Packer()
            # High max_weight because we only care about dimensions
            packer.add_bin(Bin('TestBin', box_dim[0], box_dim[1], box_dim[2], 99999))
            
            for item in current_items_base:
                packer.add_item(item)
            
            packer.pack()
            result_bin = packer.bins[0]
            
            # --- SCORING SYSTEM ---
            count = len(result_bin.items)
            bb_vol, bb_dims = get_bounding_box_stats(result_bin)
            
            # Priority 1: Most Items Packed
            if count > best_item_count:
                best_item_count = count
                min_bounding_vol = bb_vol
                best_bin = result_bin
            # Priority 2: If Counts are equal, prefer the TIGHTEST pack (Smallest Bounding Box)
            elif count == best_item_count:
                if bb_vol < min_bounding_vol:
                    min_bounding_vol = bb_vol
                    best_bin = result_bin

    progress_bar.progress(100)
    status_text.text("Optimization Complete.")

    # 4. Render Results
    if best_bin:
        b = best_bin
        bb_vol, bb_dims = get_bounding_box_stats(b)
        
        # Get the dimensions of the WINNING container orientation
        used_w, used_h, used_d = float(b.width), float(b.height), float(b.depth)

        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Items Packed", f"{len(b.items)} / {len(raw_items)}")
        c2.metric("Bounding Box (Actual Size Used)", f"{bb_dims[0]:.2f} x {bb_dims[1]:.2f} x {bb_dims[2]:.2f}")
        
        # Detect Rotation
        was_rotated = sorted([used_w, used_h, used_d]) == sorted(original_dims) and [used_w, used_h, used_d] != original_dims
        
        if was_rotated:
            st.info(f"ℹ️ **Auto-Rotation:** Box rotated to **{used_w:.2f} x {used_h:.2f} x {used_d:.2f}**")
        else:
            c3.metric("Box Orientation", f"{used_w:.2f}x{used_h:.2f}x{used_d:.2f}")

        if len(b.unfitted_items) > 0:
            st.error(f"❌ Could not fit: " + ", ".join([i.name for i in b.unfitted_items]))
        else:
            st.success("✅ Success! All items fit perfectly.")

        # 3D Plot
        fig = go.Figure()
        
        # Container (Grey Transparent)
        fig.add_trace(get_cube_mesh([used_w, used_h, used_d], (0,0,0), 'grey', 0.05, 'Container'))
        
        # Bounding Box (Red Wireframe)
        fig.add_trace(get_cube_mesh(bb_dims, (0,0,0), 'red', 1.0, 'Bounding Box', wireframe=True))
        
        # Items (Colored)
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3']
        for idx, item in enumerate(b.items):
            dims = [float(item.width), float(item.height), float(item.depth)]
            pos = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
            fig.add_trace(get_cube_mesh(dims, pos, colors[idx % len(colors)], 1.0, item.name))

        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[0, used_w], title='W'),
                yaxis=dict(range=[0, used_h], title='H'),
                zaxis=dict(range=[0, used_d], title='D'),
                aspectmode='data'
            ),
            height=700,
            margin=dict(l=0, r=0, b=0, t=0),
            title=f"Best Fit ({len(b.items)} items)"
        )
        st.plotly_chart(fig, use_container_width=True)
