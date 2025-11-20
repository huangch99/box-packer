import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="Precision 3D Packer", layout="wide")
st.title("📦 Precision 3D Packer (Final Working Version)")

# --- SIDEBAR ---
st.sidebar.header("1. Container (Fixed)")
cont_l = st.sidebar.number_input("Length (X)", value=8.25, step=0.01, format="%.2f")
cont_w = st.sidebar.number_input("Width (Y)", value=6.38, step=0.01, format="%.2f")
cont_h = st.sidebar.number_input("Height (Z)", value=3.75, step=0.01, format="%.2f")

st.sidebar.header("2. Items")
default_items = """MEC102A, 7, 3.7, 2.92
MSC137A, 3.6, 3.35, 3.55
MAC105A, 4, 2.8, 0.8"""
items_text = st.sidebar.text_area("List (Name, L, W, H)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- VISUALIZATION HELPER ---
def get_cube_trace(size, position, color, name="", is_wireframe=False):
    dx, dy, dz = size
    x, y, z = position
    if is_wireframe:
        x_lines = [x, x+dx, x+dx, x, x,    x, x+dx, x+dx, x, x,    x, x, x+dx, x+dx, x+dx, x+dx]
        y_lines = [y, y, y+dy, y+dy, y,    y, y, y+dy, y+dy, y,    y, y, y, y, y+dy, y+dy]
        z_lines = [z, z, z, z, z,          z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz]
        return go.Scatter3d(x=x_lines, y=y_lines, z=z_lines, mode='lines', line=dict(color='black', width=5), name=name, hoverinfo='name')
    else:
        x_corners = [x, x+dx, x+dx, x,    x, x+dx, x+dx, x]
        y_corners = [y, y,    y+dy, y+dy, y, y,    y+dy, y+dy]
        z_corners = [z, z,    z,    z,    z+dz, z+dz, z+dz, z+dz]
        i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        hover_text = f"<b>{name}</b><br>Size: {dx:.3f}x{dy:.3f}x{dz:.3f}<br>Pos: {x:.2f}, {y:.2f}, {z:.2f}"
        return go.Mesh3d(x=x_corners, y=y_corners, z=z_corners, i=i, j=j, k=k, color=color, opacity=1.0, name=name, text=name, hovertemplate=hover_text, showscale=False)

# --- MAIN LOGIC ---
if run_btn:
    # 1. PARSING
    # We subtract a tiny tolerance to prevent 3.75000001 vs 3.75 issues
    TOLERANCE = 0.001 
    raw_items_data = []
    try:
        lines = items_text.strip().split('\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 4:
                name = parts[0].strip()
                l = float(parts[1].strip()) - TOLERANCE
                w = float(parts[2].strip()) - TOLERANCE
                h = float(parts[3].strip()) - TOLERANCE
                raw_items_data.append({'name': name, 'l': l, 'w': w, 'h': h})
    except Exception as e: st.error(f"Error: {e}"); st.stop()
    
    if not raw_items_data: st.stop()

    # 2. DEEP SOLVER STRATEGY
    # Mode A: Standard (X=L, Y=W, Z=H)
    # Mode B: Width-Saver (X=L, Y=H, Z=W) -> Forces the AI to minimize Width usage
    simulation_modes = [
        {'name': 'Standard', 'dims': [cont_l, cont_w, cont_h], 'map': 'LWH'},
        {'name': 'Width-Saver', 'dims': [cont_l, cont_h, cont_w], 'map': 'LHW'}
    ]
    
    # 3. ORDER PERMUTATIONS
    permutations = list(itertools.permutations(raw_items_data))
    
    best_solution = None
    best_count = -1
    
    progress = st.progress(0)
    total_checks = len(simulation_modes) * len(permutations)
    checks = 0

    for mode in simulation_modes:
        sim_dims = mode['dims']
        
        for order in permutations:
            checks += 1
            if checks % 5 == 0: progress.progress(checks / total_checks)
            
            packer = Packer()
            # FIXED: Removed invalid 'number_of_decimals' argument
            packer.add_bin(Bin('SimBin', sim_dims[0], sim_dims[1], sim_dims[2], 9999))
            
            for d in order:
                packer.add_item(Item(d['name'], d['l'], d['w'], d['h'], 1))
            
            packer.pack()
            b = packer.bins[0]
            
            if len(b.items) > best_count:
                best_count = len(b.items)
                
                # Map Coordinates Back to Reality
                visual_items = []
                for item in b.items:
                    # Get dimensions (d) and position (p) from Simulation
                    d = [float(item.width), float(item.height), float(item.depth)]
                    p = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
                    
                    if mode['map'] == 'LHW':
                        # Simulation: X=Length, Y=Height, Z=Width
                        # Reality:    X=Length, Y=Width,  Z=Height
                        real_d = [d[0], d[2], d[1]]
                        real_p = [p[0], p[2], p[1]]
                    else:
                        real_d = d
                        real_p = p
                        
                    visual_items.append({'name': item.name, 'dim': real_d, 'pos': real_p})
                
                best_solution = {'items': visual_items, 'unfitted': b.unfitted_items, 'mode': mode['name']}
            
            # If we fit everything, stop immediately
            if best_count == len(raw_items_data):
                break
        if best_count == len(raw_items_data): break
            
    progress.empty()

    # 4. RESULTS
    if best_solution:
        count = len(best_solution['items'])
        c1, c2 = st.columns(2)
        c1.metric("Result", f"{count} / {len(raw_items_data)} Items")
        
        if count == len(raw_items_data):
            st.success(f"✅ **Success!** All items fit using {best_solution['mode']} Logic.")
        else:
            st.error("❌ Could not fit all items.")
            if best_solution['unfitted']:
                st.write("Unfitted: " + ", ".join([i.name for i in best_solution['unfitted']]))

        # 5. PLOT
        fig = go.Figure()
        fig.add_trace(get_cube_trace([cont_l, cont_w, cont_h], (0,0,0), 'black', "Container", True))
        
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA']
        for i, dat in enumerate(best_solution['items']):
            # Add tolerance back so it looks correct
            d = [dat['dim'][0]+TOLERANCE, dat['dim'][1]+TOLERANCE, dat['dim'][2]+TOLERANCE]
            fig.add_trace(get_cube_trace(d, dat['pos'], colors[i%4], dat['name']))

        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[0, cont_l], title='Length (X)'),
                yaxis=dict(range=[0, cont_w], title='Width (Y)'),
                zaxis=dict(range=[0, cont_h], title='Height (Z)'),
                aspectmode='manual', aspectratio=dict(x=cont_l, y=cont_w, z=cont_h)
            ),
            height=700, margin=dict(l=0,r=0,b=0,t=0),
            title=f"Packed View ({cont_l}x{cont_w}x{cont_h})"
        )
        st.plotly_chart(fig, use_container_width=True)
