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
    
    strateg
