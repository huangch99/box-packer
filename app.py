import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import copy
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="Smart 3D Packer", layout="wide")
st.title("📦 Smart 3D Packing (Strict Logic Mode)")
st.write("""
**Current Logic:**
1. Sort items by **Volume** (Biggest First).
2. Attempt to place items **Side-by-Side** (Floor) first.
3. If Floor fails, attempt to **Stack**.
4. Test all Box Rotations to find the one that allows the most Floor placements.
""")

# --- SIDEBAR ---
st.sidebar.header("1. Container Size")
bin_w = st.sidebar.number_input("Width", value=8.25, step=0.01, format="%.2f")
bin_h = st.sidebar.number_input("Height", value=6.38, step=0.01, format="%.2f")
bin_d = st.sidebar.number_input("Depth", value=3.75, step=0.01, format="%.2f")

st.sidebar.header("2. Items")
# Your specific puzzle items
default_items = """MSC137A, 3.6, 3.55, 3.35
MEC102A, 7, 3.7, 2.92
MAC105A, 4, 2.8, 0.8"""
items_text = st.sidebar.text_area("List (Name, W, H, D)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- HELPER: BOUNDING BOX ---
def get_bounding_box_stats(bin_obj):
    if not bin_obj.items: return 0, (0,0,0)
    max_x, max_y, max_z = 0, 0, 0
    for item in bin_obj.items:
        dim_w, dim_h, dim_d = float(item.width), float(item.height), float(item.depth)
        pos_x, pos_y, pos_z = float(item.position[0]), float(item.position[1]), float(item.position[2])
        if pos_x + dim_w > max_x: max_x = pos_x + dim_w
        if pos_y + dim_h > max_y: max_y = pos_y + dim_h
        if pos_z + dim_d > max_z: max_z = pos_z + dim_d
    return (max_x * max_y * max_z), (max_x, max_y, max_z)

# --- HELPER: VISUALIZATION ---
def get_cube_mesh(size, position, color, opacity=1.0, name="", wireframe=False):
    dx, dy, dz = size
    x, y, z = position
    if wireframe:
        return go.Scatter3d(
            x=[x, x+dx, x+dx, x, x,  x, x+dx, x+dx, x, x,  x, x, x+dx, x+dx, x+dx, x+dx],
            y=[y, y, y+dy, y+dy, y,  y, y, y+dy, y+dy, y,  y, y, y, y, y+dy, y+dy],
            z=[z, z, z, z, z,        z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz],
            mode='lines', line=dict(color=color, width=5), name=name, hoverinfo='name'
        )
    x_coords = [x, x+dx, x+dx, x,    x, x+dx, x+dx, x]
    y_coords = [y, y,    y+dy, y+dy, y, y,    y+dy, y+dy]
    z_coords = [z, z,    z,    z,    z+dz, z+dz, z+dz, z+dz]
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    return go.Mesh3d(x=x_coords, y=y_coords, z=z_coords, i=i, j=j, k=k, color=color, opacity=opacity, name=name, showscale=False, hoverinfo='name')

# --- MAIN ALGORITHM ---
if run_btn:
    # 1. PARSE AND TOLERANCE ADJUSTMENT
    # We subtract 0.01 from items to handle tight fits (3.7 vs 3.75)
    TOLERANCE = 0.01 
    raw_items = []
    try:
        lines = items_text.strip().split('\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 4:
                name = parts[0].strip()
                w = float(parts[1].strip()) - TOLERANCE
                h = float(parts[2].strip()) - TOLERANCE
                d = float(parts[3].strip()) - TOLERANCE
                raw_items.append(Item(name, w, h, d, 1))
    except Exception as e:
        st.error(f"Error: {e}"); st.stop()
    
    if not raw_items: st.stop()

    # 2. RULE 1: SORT BY VOLUME (Biggest First)
    # This ensures the logic: "Find biggest volume item and put in box first"
    raw_items.sort(key=lambda x: x.width * x.height * x.depth, reverse=True)

    # 3. PREPARE SIMULATION
    # We test all 6 Box Orientations. This simulates "Try to rotate items to fit next to each other"
    # because it changes which axis is available for the 'next' item.
    original_dims = [bin_w, bin_h, bin_d]
    box_orientations = list(set(itertools.permutations(original_dims)))
    
    best_bin = None
    best_score = -1 # Higher is better
    
    # 4. RUN SIMULATION LOOP
    progress = st.progress(0)
    
    for i, box_dim in enumerate(box_orientations):
        progress.progress((i+1) / len(box_orientations))
        
        packer = Packer()
        packer.add_bin(Bin('TestBin', box_dim[0], box_dim[1], box_dim[2], 99999))
        for item in raw_items:
            packer.add_item(item)
        
        packer.pack()
        b = packer.bins[0]
        
        # --- CUSTOM SCORING LOGIC ---
        
        # A. Must pack as many items as possible
        count = len(b.items)
        
        # B. "Floor Count" (Rule 3)
        # How many items are touching the floor (Z=0)?
        # We prioritize layouts where items are Side-by-Side rather than stacked.
        floor_items = 0
        max_z = 0
        for item in b.items:
            if float(item.position[2]) <= 0.01: # Effectively 0
                floor_items += 1
            # Track stack height
            top_z = float(item.position[2]) + float(item.depth) # Depth is Z in py3dbp
            if top_z > max_z: max_z = top_z

        # C. Score Calculation
        # 1. Primary: Count (Multiplier 1000)
        # 2. Secondary: Floor Items (Multiplier 10) -> Enforces "Place on floor first"
        # 3. Tie-Breaker: Lowest Max Height (Multiplier -1) -> Tighter packing
        score = (count * 1000) + (floor_items * 10) - max_z
        
        if score > best_score:
            best_score = score
            best_bin = b
            
    progress.empty()

    # 5. DISPLAY RESULTS
    if best_bin:
        b = best_bin
        bb_vol, bb_dims = get_bounding_box_stats(b)
        used_w, used_h, used_d = float(b.width), float(b.height), float(b.depth)

        c1, c2, c3 = st.columns(3)
        c1.metric("Items Packed", f"{len(b.items)} / {len(raw_items)}")
        
        # Calculate how many on floor for display
        final_floor_count = sum(1 for i in b.items if float(i.position[2]) <= 0.01)
        c2.metric("Items on Floor", f"{final_floor_count} (Side-by-Side)")
        
        was_rotated = sorted([used_w, used_h, used_d]) == sorted(original_dims) and [used_w, used_h, used_d] != original_dims
        if was_rotated:
            st.info(f"ℹ️ **Auto-Rotation:** Box rotated to **{used_w:.2f} x {used_h:.2f} x {used_d:.2f}** to allow side-by-side fitting.")
        else:
            c3.metric("Box Orientation", f"{used_w:.2f}x{used_h:.2f}x{used_d:.2f}")

        if len(b.unfitted_items) > 0:
            st.error(f"❌ Could not fit: " + ", ".join([i.name for i in b.unfitted_items]))
        else:
            st.success("✅ All items fit according to rules!")

        # 3D Visual
        fig = go.Figure()
        fig.add_trace(get_cube_mesh([used_w, used_h, used_d], (0,0,0), 'grey', 0.05, 'Container'))
        fig.add_trace(get_cube_mesh(bb_dims, (0,0,0), 'red', 1.0, 'Bounding Box', wireframe=True))
        
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A']
        for idx, item in enumerate(b.items):
            # Add tolerance back for visual (optional, but looks nicer)
            dims = [float(item.width)+TOLERANCE, float(item.height)+TOLERANCE, float(item.depth)+TOLERANCE]
            pos = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
            fig.add_trace(get_cube_mesh(dims, pos, colors[idx % len(colors)], 1.0, item.name))

        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[0, used_w], title='Width'),
                yaxis=dict(range=[0, used_h], title='Height'),
                zaxis=dict(range=[0, used_d], title='Depth'),
                aspectmode='data'
            ),
            height=700, margin=dict(l=0, r=0, b=0, t=0)
        )
        st.plotly_chart(fig, use_container_width=True)
