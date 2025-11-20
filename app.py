import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="Solver 3D Packer", layout="wide")
st.title("📦 3D Packer (Virtual Rotation Solver)")
st.markdown("This solver runs internal simulations with swapped axes to trick the AI into finding the perfect fit, then maps it back to your fixed container.")

# --- SIDEBAR INPUTS ---
st.sidebar.header("1. Container Dimensions (Fixed)")
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
        # Black Wireframe for Container
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
    # 1. PARSING (Tiny Tolerance for float math)
    TOLERANCE = 0.002 
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
    except Exception as e: st.error(f"Input Error: {e}"); st.stop()
    
    if not raw_items: st.stop()

    # 2. THE VIRTUAL SOLVER
    # We try 2 simulations: 
    # A: Normal (L, W, H)
    # B: Swapped X/Y (W, L, H) -> This tricks the AI to fill the 'Width' first.
    
    simulation_configs = [
        {'dims': [cont_l, cont_w, cont_h], 'map_back': False}, # Standard
        {'dims': [cont_w, cont_l, cont_h], 'map_back': True}   # Virtual Rotation (Swap X/Y)
    ]
    
    # We also try all item orders
    item_orders = list(itertools.permutations(raw_items))
    
    best_solution = None
    best_count = -1
    
    progress_bar = st.progress(0)
    total_checks = len(simulation_configs) * len(item_orders)
    check_count = 0

    for config in simulation_configs:
        sim_dims = config['dims']
        
        for order in item_orders:
            check_count += 1
            if check_count % 5 == 0:
                progress_bar.progress(check_count / total_checks)

            packer = Packer()
            packer.add_bin(Bin('SimBin', sim_dims[0], sim_dims[1], sim_dims[2], 9999))
            for item in order:
                packer.add_item(item)
            
            packer.pack()
            b = packer.bins[0]
            
            # Check if we found a better solution
            if len(b.items) > best_count:
                best_count = len(b.items)
                
                # PREPARE DATA FOR VISUALIZATION
                # If we used the "Swapped" simulation, we must swap X and Y back 
                # so it fits the user's original Fixed Container.
                
                final_items_data = []
                for item in b.items:
                    # Get calculated dimensions and position
                    i_dims = [float(item.width), float(item.height), float(item.depth)]
                    i_pos = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
                    
                    if config['map_back']:
                        # Swap X and Y coordinates and dimensions
                        # New X = Old Y, New Y = Old X
                        final_dims = [i_dims[1], i_dims[0], i_dims[2]] 
                        final_pos = [i_pos[1], i_pos[0], i_pos[2]]
                    else:
                        final_dims = i_dims
                        final_pos = i_pos
                        
                    final_items_data.append({
                        'name': item.name,
                        'dims': final_dims,
                        'pos': final_pos
                    })
                
                best_solution = {
                    'items': final_items_data,
                    'unfitted': b.unfitted_items
                }
            
            # Stop if perfect
            if best_count == len(raw_items):
                break
        if best_count == len(raw_items):
            break

    progress_bar.empty()

    # 3. RENDER RESULTS
    if best_solution:
        packed_count = len(best_solution['items'])
        c1, c2 = st.columns(2)
        c1.metric("Items Packed", f"{packed_count} / {len(raw_items)}")
        
        if packed_count == len(raw_items):
            st.success("✅ **Success!** The Virtual Solver found a valid fit.")
        else:
            st.error(f"❌ Could not fit all items. Best attempt: {packed_count}.")
            if best_solution['unfitted']:
                 st.write("Unfitted: " + ", ".join([i.name for i in best_solution['unfitted']]))

        # 4. VISUALIZATION
        fig = go.Figure()
        
        # Draw ORIGINAL Fixed Container
        fig.add_trace(get_cube_trace([cont_l, cont_w, cont_h], (0,0,0), 'black', "Container", True))
        
        # Draw Items (mapped back to original space)
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A']
        for idx, item_data in enumerate(best_solution['items']):
            # Add tolerance back for visual
            d = item_data['dims']
            p = item_data['pos']
            vis_dims = [d[0]+TOLERANCE, d[1]+TOLERANCE, d[2]+TOLERANCE]
            
            fig.add_trace(get_cube_trace(vis_dims, p, colors[idx % len(colors)], item_data['name']))

        fig.update_layout(
            scene=dict(
                xaxis=dict(range=[0, cont_l], title='Length (X)'),
                yaxis=dict(range=[0, cont_w], title='Width (Y)'),
                zaxis=dict(range=[0, cont_h], title='Height (Z)'),
                aspectmode='manual',
                aspectratio=dict(x=cont_l, y=cont_w, z=cont_h)
            ),
            height=700, margin=dict(l=0, r=0, b=0, t=0),
            title=f"Fixed Container View ({cont_l}x{cont_w}x{cont_h})"
        )
        st.plotly_chart(fig, use_container_width=True)
