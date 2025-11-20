import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import random
import copy

# --- PAGE CONFIG ---
st.set_page_config(page_title="Smart 3D Packer", layout="wide")
st.title("📦 Smart 3D Packing Simulator")

# --- SIDEBAR ---
st.sidebar.header("1. Container Size")
bin_w = st.sidebar.number_input("Width", value=50, step=1)
bin_h = st.sidebar.number_input("Height", value=50, step=1)
bin_d = st.sidebar.number_input("Depth", value=50, step=1)

st.sidebar.header("2. Packing Strategy")
enable_optimization = st.sidebar.checkbox("🚀 AI Auto-Optimize", value=True, help="Tries 50+ variations to find the best layout.")
iterations = st.sidebar.slider("Optimization Attempts", 10, 100, 20) if enable_optimization else 1

st.sidebar.header("3. Items")
default_items = """Laptop, 30, 2, 20
ShoeBox, 20, 10, 30
Cube, 15, 15, 15
Tube, 5, 5, 45
BigBox, 25, 25, 25"""
items_text = st.sidebar.text_area("List (Name, W, H, D)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- VISUALIZATION FUNCTION ---
def get_cube_mesh(size, position, color, opacity=1.0, name=""):
    dx, dy, dz = size
    x, y, z = position
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

# --- PACKING LOGIC ---
def solve_packing(items, box_size, use_random=False):
    """Runs a single packing simulation."""
    packer = Packer()
    # Large max_weight so we only focus on dimensions
    packer.add_bin(Bin('MainBin', box_size[0], box_size[1], box_size[2], 100000))
    
    # Add items
    current_items = copy.deepcopy(items)
    if use_random:
        random.shuffle(current_items)
    
    for item in current_items:
        packer.add_item(item)
        
    packer.pack()
    return packer.bins[0]

# --- MAIN APP ---
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
                raw_items.append(Item(name, w, h, d, 1)) # Weight 1
    except Exception as e:
        st.error(f"Formatting Error: {e}")
        st.stop()

    if not raw_items:
        st.warning("Please enter at least one item.")
        st.stop()

    # 2. Optimization Loop
    box_dims = (bin_w, bin_h, bin_d)
    best_bin = None
    best_score = -1 # Score = Number of items packed
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Strategy 1: Standard (Largest to Smallest - Default)
    # py3dbp sorts internally, but we pass raw list first
    
    strategies = range(iterations) if enable_optimization else range(1)
    
    for i in strategies:
        if enable_optimization:
            status_text.text(f"Simulating layout {i+1}/{iterations}...")
            progress_bar.progress((i+1)/iterations)
        
        # Run Solver
        result_bin = solve_packing(raw_items, box_dims, use_random=(i > 0))
        
        # Scoring: Prioritize Count first, then Volume Utilization
        packed_count = len(result_bin.items)
        utilization = result_bin.get_volume_utilization()
        
        # Simple score: Count * 1000 + Utilization
        score = (packed_count * 1000) + utilization
        
        if score > best_score:
            best_score = score
            best_bin = result_bin

    progress_bar.empty()
    status_text.empty()

    # 3. Display Results
    if best_bin:
        b = best_bin
        packed_count = len(b.items)
        total_count = len(raw_items)
        
        # Metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Items Packed", f"{packed_count} / {total_count}")
        c2.metric("Volume Used", f"{b.get_volume_utilization():.2f}%")
        c3.metric("Attempts", iterations if enable_optimization else 1)

        if len(b.unfitted_items) > 0:
            st.warning(f"⚠️ Could not fit {len(b.unfitted_items)} items: " + ", ".join([i.name for i in b.unfitted_items]))
        else:
            st.success("✅ All items fit perfectly!")

        # 4. 3D Visualization
        fig = go.Figure()
        
        # Draw Container
        fig.add_trace(get_cube_mesh([bin_w, bin_h, bin_d], (0,0,0), 'grey', 0.1, 'Container'))
        
        # Draw Items
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
            title=f"Best Layout Found (Sorted by {'Random' if enable_optimization else 'Default'})"
        )
        st.plotly_chart(fig, use_container_width=True)
