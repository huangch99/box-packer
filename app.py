import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import copy
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="True-Scale 3D Packer", layout="wide")
st.title("📦 Smart 3D Packing (True-Scale Visuals)")

# --- SIDEBAR ---
st.sidebar.header("1. Container Dimensions")
# Switched to Length/Width/Height for clarity
cont_l = st.sidebar.number_input("Length (X)", value=8.25, step=0.01, format="%.2f")
cont_w = st.sidebar.number_input("Width (Y)", value=6.38, step=0.01, format="%.2f")
cont_h = st.sidebar.number_input("Height (Z)", value=3.75, step=0.01, format="%.2f")

st.sidebar.header("2. Items")
default_items = """MSC137A, 3.6, 3.55, 3.35
MEC102A, 7, 3.7, 2.92
MAC105A, 4, 2.8, 0.8"""
items_text = st.sidebar.text_area("List (Name, L, W, H)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- HELPER: VISUALIZATION ---
def get_cube_trace(size, position, color, name="", is_wireframe=False, opacity=1.0):
    dx, dy, dz = size
    x, y, z = position
    
    # Define the 8 corners of the cube
    x_corners = [x, x+dx, x+dx, x,    x, x+dx, x+dx, x]
    y_corners = [y, y,    y+dy, y+dy, y, y,    y+dy, y+dy]
    z_corners = [z, z,    z,    z,    z+dz, z+dz, z+dz, z+dz]

    if is_wireframe:
        # Draw linear edges for the container (Clearer than mesh)
        # Order of points to draw a continuous line for a cube
        x_lines = [x, x+dx, x+dx, x, x,    x, x+dx, x+dx, x, x,    x, x, x+dx, x+dx, x+dx, x+dx]
        y_lines = [y, y, y+dy, y+dy, y,    y, y, y+dy, y+dy, y,    y, y, y, y, y+dy, y+dy]
        z_lines = [z, z, z, z, z,          z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz]
        
        return go.Scatter3d(
            x=x_lines, y=y_lines, z=z_lines,
            mode='lines',
            line=dict(color='black', width=4),
            name=name, hoverinfo='name'
        )
    
    else:
        # Solid Item Mesh
        i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        
        # Hover text showing dimensions
        hover_text = f"<b>{name}</b><br>Packed Size: {dx:.2f} x {dy:.2f} x {dz:.2f}"
        
        return go.Mesh3d(
            x=x_corners, y=y_corners, z=z_corners,
            i=i, j=j, k=k,
            color=color, opacity=opacity, 
            name=name,
            text=name,
            hovertemplate=hover_text,
            showscale=False
        )

# --- MAIN ALGORITHM ---
if run_btn:
    # 1. PARSE (Subtract Tolerance)
    # Using tolerance 0.005 to handle floating point limits
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
        st.error(f"Error: {e}"); st.stop()
    
    if not raw_items: st.stop()

    # 2. SORT (Rule 1: Biggest Volume First)
    raw_items.sort(key=lambda x: x.width * x.height * x.depth, reverse=True)

    # 3. SIMULATION (Container Rotation)
    # Input: Length(W in lib), Width(H in lib), Height(D in lib)
    original_dims = [cont_l, cont_w, cont_h]
    box_orientations = list(set(itertools.permutations(original_dims)))
    
    best_bin = None
    best_score = -1
    
    progress = st.progress(0)
