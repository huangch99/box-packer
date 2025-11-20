import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import random
import copy
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="Smart 3D Packer", layout="wide")
st.title("📦 Smart 3D Packing (Floor-Filling Mode)")

# --- SIDEBAR ---
st.sidebar.header("1. Container Size")
bin_w = st.sidebar.number_input("Width", value=50.00, step=0.1, format="%.2f")
bin_h = st.sidebar.number_input("Height", value=50.00, step=0.1, format="%.2f")
bin_d = st.sidebar.number_input("Depth", value=50.00, step=0.1, format="%.2f")

st.sidebar.header("2. Optimization")
enable_optimization = st.sidebar.checkbox("🚀 AI Auto-Optimize", value=True, help="Tries different sorting strategies to find the best fit.")
iterations = st.sidebar.slider("Attempts", 5, 50, 15) if enable_optimization else 1

st.sidebar.header("3. Items")
default_items = """Laptop, 30.5, 2.25, 20.0
ShoeBox, 20.1, 10.0, 30.5
Cube, 15.0, 15.0, 15.0
Tube, 5.5, 5.5, 45.0
BigBox, 25.0, 25.0, 25.0"""
items_text = st.sidebar.text_area("List (Name, W, H, D)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- LOGIC: BOUNDING BOX ---
def get_bounding_box_stats(bin_obj):
    """Calculates the tightest box that surrounds all packed items."""
    if not bin_obj.items:
        return 0, (0,0,0)

    max_x, max_y, max_z = 0, 0, 0
    
    for item in bin_obj.items:
        dim_w, dim_h, dim_d = float(item.width), float(item.height), float(item.depth)
        pos_x, pos_y, pos_z = float(item.position[0]), float(item.position[1]), float(item.position[2])
        
        if pos_x + dim_w > max_x: max_x = pos_x + dim_w
        if pos_y + dim_h > max_y: max_y = pos_y + dim_h
        if pos_z + dim_d > max_z: max_z = pos_z + dim_d
        
    used_volume = max_x * max_y * max_z
    return used_volume, (max_x, max_y, max_z)

# --- VISUALIZATION FUNCTION ---
def get_cube_mesh(size, position, color, opacity=1.0, name="", wireframe=False):
    dx, dy, dz = size
    x, y, z = position
    
    if wireframe:
        return go.Scatter3d(
            x=[x, x+dx, x+dx, x, x,  x, x+dx, x+dx, x, x,  x, x, x+dx, x+dx, x+dx, x+dx],
            y=[y, y, y+dy, y+dy, y,  y, y, y+dy, y+dy, y,  y, y, y, y, y+dy, y+dy],
            z=[z, z, z, z, z,        z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz],
            mode='lines',
            line=dict(color=color, width=5),
            name=name, hoverinfo='name'
        )

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

# --- MAIN LOGIC ---
if run_btn:
    # 1. Parse Items
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

    # 2. Prepare Variations
    original_dims = [bin_w, bin_h, bin_d]
    box_orientations = list(set(itertools.permutations(original_dims)))
    
    best_bin = None
    best_item_count = -1
    min_bounding_vol = float('inf') 
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    strategies_count = iterations if enable_optimization else 1
    total_checks = strategies_count * len(box_orientations)
    check_idx = 0

    # 3. Run Strategies
    for i in range(strategies_count):
        current_items_base = copy.deepcopy(raw_items)
        
        # --- STRATEGY LOGIC ---
        # To ensure side-by-side placement, we prioritize Footprint (W*D) sorting.
        
        if i == 0:
            # Strategy A: AREA DESCENDING (Best for Floor Filling / Side-by-Side)
            # Sorts by Bottom Area (Width * Depth)
            # This makes large flat items go first, creating a "floor"
            current_items_base.sort(key=lambda x: float(x.width)*float(x.depth), reverse=True)
            strategy_name = "Floor Filler (Area)"
            
        elif i == 1:
            # Strategy B: HEIGHT DESCENDING (Layering)
            # Places tall items first to establish 'walls', or ensures similar heights group together
            current_items_base.sort(key=lambda x: float(x.height), reverse=True)
            strategy_name = "Height Layering"
            
        elif i == 2:
            # Strategy C: VOLUME DESCENDING (Standard)
            current_items_base.sort(key=lambda x: float(x.width)*float(x.height)*float(x.depth), reverse=True)
            strategy_name = "Volume Descending"
            
        else:
            # Strategy D: RANDOM (Brute force)
            random.shuffle(current_items_base)
            strategy_name = "Random Shuffle"
            
        for box_dim in box_orientations:
            check_idx += 1
            if check_idx % 2 == 0:
                progress_bar.progress(min(check_idx / total_checks, 1.0))
                status_text.text(f"Trying: {strategy_name} in {box_dim}...")

            packer = Packer()
            # 99999 weight ensures we only care about size
            packer.add_bin(Bin('TestBin', box_dim[0], box_dim[1], box_dim[2], 99999))
            
            for item in current_items_base:
                packer.add_item(item)
            
            packer.pack()
            result_bin = packer.bins[0]
            
            count = len(result_bin.items)
            bb_vol, bb_dims = get_bounding_box_stats(result_bin)
            
            # Score: Max Count > Min Volume
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
        used_w = float(b.width)
        used_h = float(b.height)
        used_d = float(b.depth)

        c1, c2, c3 = st.columns(3)
        c1.metric("Items Packed", f"{len(b.items)} / {len(raw_items)}")
        c2.metric("Bounding Box", f"{bb_dims[0]:.2f} x {bb_dims[1]:.2f} x {bb_dims[2]:.2f}")
        
        was_rotated = sorted([used_w, used_h, used_d]) == sorted(original_dims) and [used_w, used_h, used_d] != original_dims
        
        if was_rotated:
            st.info(f"ℹ️ **Auto-Rotation:** Box rotated to **{used_w:.2f} x {used_h:.2f} x {used_d:.2f}**")
        else:
            c3.metric("Box Orientation", f"{used_w:.2f}x{used_h:.2f}x{used_d:.2f}")

        if len(b.unfitted_items) > 0:
            st.warning(f"⚠️ Could not fit: " + ", ".join([i.name for i in b.unfitted_items]))
        else:
            st.success("✅ All items fit!")

        fig = go.Figure()
        
        # Draw Container
        fig.add_trace(get_cube_mesh([used_w, used_h, used_d], (0,0,0), 'grey', 0.05, 'Container'))
        
        # Draw Bounding Box
        fig.add_trace(get_cube_mesh(bb_dims, (0,0,0), 'red', 1.0, 'Bounding Box', wireframe=True))
        
        # Draw Items
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
