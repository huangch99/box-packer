import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="Precision 3D Packer", layout="wide")
st.title("📦 Precision 3D Packing")

# --- SIDEBAR ---
st.sidebar.header("1. Container Dimensions")
cont_l = st.sidebar.number_input("Length (X)", value=8.25, step=0.01, format="%.2f")
cont_w = st.sidebar.number_input("Width (Y)", value=6.38, step=0.01, format="%.2f")
cont_h = st.sidebar.number_input("Height (Z)", value=3.75, step=0.01, format="%.2f")

st.sidebar.header("2. Options")
# NEW: Checkbox to control container rotation
allow_rotation = st.sidebar.checkbox("Allow Container Rotation?", value=False, 
    help="If checked, the AI will try tipping the box on its side (swapping L/W/H) to fit items.")

st.sidebar.header("3. Items")
default_items = """MSC137A, 3.6, 3.55, 3.35
MEC102A, 7, 3.7, 2.92
MAC105A, 4, 2.8, 0.8"""
items_text = st.sidebar.text_area("List (Name, L, W, H)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- HELPER: VISUALIZATION ---
def get_cube_trace(size, position, color, name="", is_wireframe=False, opacity=1.0):
    dx, dy, dz = size
    x, y, z = position
    
    if is_wireframe:
        # Draw linear edges (Black Wireframe)
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
    # 1. TOLERANCE & PARSING
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

    # 2. SORT STRATEGY (Biggest Volume First)
    raw_items.sort(key=lambda x: x.width * x.height * x.depth, reverse=True)

    # 3. CONTAINER ORIENTATION LOGIC
    original_dims = [cont_l, cont_w, cont_h]
    
    if allow_rotation:
        # Try all 6 permutations of (L, W, H)
        box_orientations = list(set(itertools.permutations(original_dims)))
    else:
        # STRICT MODE: Only use the exact dimensions provided
        box_orientations = [original_dims]
    
    best_bin = None
    best_score = -1
    
    # 4. SIMULATION LOOP
    for box_dim in box_orientations:
        packer = Packer()
        # Create Bin with (Width=X, Height=Y, Depth=Z) mapping
        packer.add_bin(Bin('TestBin', box_dim[0], box_dim[1], box_dim[2], 99999))
        
        for item in raw_items:
            packer.add_item(item)
        
        packer.pack()
        b = packer.bins[0]
        
        # Scoring: Maximise Packed Count, then Maximise Floor Usage
        count = len(b.items)
        floor_items = sum(1 for item in b.items if float(item.position[2]) <= 0.01)
        
        # Simple Score
        score = (count * 1000) + floor_items
        
        if score > best_score:
            best_score = score
            best_bin = b

    # 5. RESULTS & VISUALIZATION
    if best_bin:
        b = best_bin
        
        # Dimensions actually used by the logic
        used_l, used_w, used_h = float(b.width), float(b.height), float(b.depth)

        # Display Stats
        c1, c2, c3 = st.columns(3)
        c1.metric("Items Packed", f"{len(b.items)} / {len(raw_items)}")
        c2.metric("Items on Floor", sum(1 for i in b.items if float(i.position[2]) <= 0.01))
        
        # Warn if rotation happened (only possible if checkbox was on)
        if allow_rotation and [used_l, used_w, used_h] != original_dims:
             st.warning(f"⚠️ Container was rotated to: {used_l:.2f} x {used_w:.2f} x {used_h:.2f}")
        else:
             c3.metric("Container Dimensions", f"{used_l:.2f} x {used_w:.2f} x {used_h:.2f}")

        if len(b.unfitted_items) > 0:
            st.error(f"❌ Failed to fit: " + ", ".join([i.name for i in b.unfitted_items]))

        # --- 3D PLOT ---
        fig = go.Figure()
        
        # Draw Container Wireframe (Black)
        fig.add_trace(get_cube_trace([used_l, used_w, used_h], (0,0,0), 'black', name="Container", is_wireframe=True))
        
        # Draw Items
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A']
        for idx, item in enumerate(b.items):
            # Add tolerance back for visual
            dims = [float(item.width)+TOLERANCE, float(item.height)+TOLERANCE, float(item.depth)+TOLERANCE]
            pos = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
            
            fig.add_trace(get_cube_trace(dims, pos, colors[idx % len(colors)], name=item.name, opacity=1.0))

        # Force Axes to match Container Size exactly
        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[0, used_l], title='Length (X)'),
                yaxis=dict(range=[0, used_w], title='Width (Y)'),
                zaxis=dict(range=[0, used_h], title='Height (Z)'),
                aspectmode='manual',
                aspectratio=dict(x=used_l, y=used_w, z=used_h)
            ),
            height=700, margin=dict(l=0, r=0, b=0, t=0),
            title=f"Visualization ({len(b.items)} items packed)"
        )
        st.plotly_chart(fig, use_container_width=True)
