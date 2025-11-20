import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import itertools
import copy

# --- PAGE CONFIG ---
st.set_page_config(page_title="Solver 3D Packer", layout="wide")
st.title("📦 3D Packer (Deep Solver - Fixed)")

# --- SIDEBAR INPUTS ---
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
        hover_text = f"<b>{name}</b><br>Size: {dx:.2f} x {dy:.2f} x {dz:.2f}<br>Pos: {x:.2f}, {y:.2f}, {z:.2f}"
        return go.Mesh3d(x=x_corners, y=y_corners, z=z_corners, i=i, j=j, k=k, color=color, opacity=1.0, name=name, text=name, hovertemplate=hover_text, showscale=False)

# --- MAIN LOGIC ---
if run_btn:
    # 1. PARSING
    TOLERANCE = 0.005 
    raw_items_data = [] # Store data, not objects yet
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
    except Exception as e:
        st.error(f"Input Error: {e}")
        st.stop()
    
    if not raw_items_data:
        st.warning("No items found. Please check input.")
        st.stop()

    # 2. DEEP SOLVER SETUP
    # Simulation Modes: Normal (X=L) vs Swapped (X=W)
    # Swapping X/Y forces the AI to optimize for Width, which helps items stand on edge.
    sim_modes = [
        {'map': 'Normal', 'dims': [cont_l, cont_w, cont_h]}, 
        {'map': 'Swapped', 'dims': [cont_l, cont_h, cont_w]} 
    ]
    
    # Generate all permutations of the DATA
    permutations = list(itertools.permutations(raw_items_data))
    
    best_solution = None
    best_count = -1
    
    # STATUS BAR
    status_text = st.empty()
    progress = st.progress(0)
    total_steps = len(sim_modes) * len(permutations)
    current_step = 0
    
    # 3. SIMULATION LOOP
    for mode in sim_modes:
        sim_dims = mode['dims']
        
        for order_data in permutations:
            current_step += 1
            if current_step % 2 == 0:
                progress.progress(current_step / total_steps)
                status_text.text(f"Testing Order {current_step}/{total_steps}...")
            
            packer = Packer()
            packer.add_bin(Bin('SimBin', sim_dims[0], sim_dims[1], sim_dims[2], 9999))
            
            # --- CRITICAL FIX: CREATE FRESH ITEMS EVERY TIME ---
            for d in order_data:
                packer.add_item(Item(d['name'], d['l'], d['w'], d['h'], 1))
            
            packer.pack()
            b = packer.bins[0]
            
            # SUCCESS CHECK
            if len(b.items) > best_count:
                best_count = len(b.items)
                
                # Prepare Visual Data (Mapped back to real coordinates)
                final_items = []
                for item in b.items:
                    # Get dimensions and positions from simulation
                    d = [float(item.width), float(item.height), float(item.depth)]
                    p = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
                    
                    # If we simulated with Swapped dimensions, un-swap them for the visual
                    if mode['map'] == 'Swapped':
                        # Sim: L, H, W (SimY is RealZ)
                        # Real: L, W, H
                        # Map SimY -> RealZ, SimZ -> RealY
                        real_d = [d[0], d[2], d[1]]
                        real_p = [p[0], p[2], p[1]]
                    else:
                        real_d = d
                        real_p = p
                    
                    final_items.append({'name': item.name, 'dim': real_d, 'pos': real_p})
                
                best_solution = {'items': final_items, 'unfitted': b.unfitted_items, 'mode': mode['map']}
                
                # Optimization: If we found a perfect fit, STOP.
                if best_count == len(raw_items_data):
                    break
        
        if best_count == len(raw_items_data):
            break

    progress.empty()
    status_text.empty()

    # 4. RESULTS
    if best_solution:
        cnt = len(best_solution['items'])
        c1, c2 = st.columns(2)
        c1.metric("Packed Items", f"{cnt} / {len(raw_items_data)}")
        
        if cnt == len(raw_items_data):
            st.success(f"✅ **Success!** Found a fit using {best_solution['mode']} axis priority.")
        else:
            st.error("❌ Could not fit all items.")
            if best_solution['unfitted']:
                 # Extract names from objects
                 names = [i.name for i in best_solution['unfitted']]
                 st.write("Unfitted: " + ", ".join(names))

        # 5. 3D PLOT
        fig = go.Figure()
        
        # Draw Container
        fig.add_trace(get_cube_trace([cont_l, cont_w, cont_h], (0,0,0), 'black', "Container", True))
        
        # Draw Items
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA']
        for i, dat in enumerate(best_solution['items']):
            # Add tolerance back for visual
            d = [dat['dim'][0]+TOLERANCE, dat['dim'][1]+TOLERANCE, dat['dim'][2]+TOLERANCE]
            fig.add_trace(get_cube_trace(d, dat['pos'], colors[i%4], dat['name']))

        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[0, cont_l], title='Length (X)'),
                yaxis=dict(range=[0, cont_w], title='Width (Y)'),
                zaxis=dict(range=[0, cont_h], title='Height (Z)'),
                aspectmode='manual', 
                aspectratio=dict(x=cont_l, y=cont_w, z=cont_h)
            ),
            height=700, margin=dict(l=0,r=0,b=0,t=0),
            title=f"Fixed Container ({cont_l} x {cont_w} x {cont_h})"
        )
        st.plotly_chart(fig, use_container_width=True)
