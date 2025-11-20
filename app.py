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
    
    for i, box_dim in enumerate(box_orientations):
        progress.progress((i+1) / len(box_orientations))
        
        # In py3dbp: Bin(name, width, height, depth)
        # Map our L,W,H to the library's W,H,D
        packer = Packer()
        packer.add_bin(Bin('TestBin', box_dim[0], box_dim[1], box_dim[2], 99999))
        for item in raw_items:
            packer.add_item(item)
        
        packer.pack()
        b = packer.bins[0]
        
        # --- SCORING ---
        count = len(b.items)
        # Floor items (Z ~ 0)
        floor_items = sum(1 for item in b.items if float(item.position[2]) <= 0.01)
        # Max Height used
        max_z = 0
        if b.items:
            max_z = max([float(it.position[2]) + float(it.depth) for it in b.items])

        # Score: Count High > Floor High > Height Low
        score = (count * 10000) + (floor_items * 100) - max_z
        
        if score > best_score:
            best_score = score
            best_bin = b
            
    progress.empty()

    # 5. DISPLAY RESULTS
    if best_bin:
        b = best_bin
        # Dimensions used by the winning box orientation
        used_l, used_w, used_h = float(b.width), float(b.height), float(b.depth)

        c1, c2, c3 = st.columns(3)
        c1.metric("Items Packed", f"{len(b.items)} / {len(raw_items)}")
        
        floor_count = sum(1 for i in b.items if float(i.position[2]) <= 0.01)
        c2.metric("Items on Floor", floor_count)
        
        was_rotated = sorted([used_l, used_w, used_h]) == sorted(original_dims) and [used_l, used_w, used_h] != original_dims
        if was_rotated:
            st.info(f"ℹ️ **Auto-Rotation:** Container rotated to **{used_l:.2f} (L) x {used_w:.2f} (W) x {used_h:.2f} (H)**")
        else:
            c3.metric("Container Orientation", f"{used_l:.2f} x {used_w:.2f} x {used_h:.2f}")

        if len(b.unfitted_items) > 0:
            st.error(f"❌ Could not fit: " + ", ".join([i.name for i in b.unfitted_items]))

        # --- 3D PLOTTING ---
        fig = go.Figure()
        
        # 1. Draw Container Wireframe (Black Outline)
        # We use the "Used" dimensions found by the AI
        fig.add_trace(get_cube_trace([used_l, used_w, used_h], (0,0,0), 'black', name="Container", is_wireframe=True))
        
        # 2. Draw Items
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3']
        
        for idx, item in enumerate(b.items):
            # Add tolerance back for visual accuracy
            dims = [float(item.width)+TOLERANCE, float(item.height)+TOLERANCE, float(item.depth)+TOLERANCE]
            pos = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
            
            fig.add_trace(get_cube_trace(
                dims, pos, 
                colors[idx % len(colors)], 
                name=item.name, 
                opacity=1.0
            ))

        # 3. FORCE TRUE SCALE (Aspect Ratio = Data)
        # This ensures 10cm looks like 10cm, not stretched
        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[0, max(used_l, used_w, used_h)], title='Length (X)'),
                yaxis=dict(range=[0, max(used_l, used_w, used_h)], title='Width (Y)'),
                zaxis=dict(range=[0, max(used_l, used_w, used_h)], title='Height (Z)'),
                aspectmode='data' # <--- THIS IS THE KEY FIX
            ),
            height=700, 
            margin=dict(l=0, r=0, b=0, t=0),
            title=f"True-Scale Visualization ({len(b.items)} Items)"
        )
        st.plotly_chart(fig, use_container_width=True)
