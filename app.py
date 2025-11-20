import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import itertools

# --- PAGE CONFIG ---
st.set_page_config(page_title="Precision 3D Packer", layout="wide")
st.title("📦 3D Packer (Step-by-Step Logic)")

# --- SIDEBAR ---
st.sidebar.header("1. Container (Fixed)")
# User Input for Container
cont_l = st.sidebar.number_input("Length (X)", value=8.25, step=0.01, format="%.2f")
cont_w = st.sidebar.number_input("Width (Y)", value=6.38, step=0.01, format="%.2f")
cont_h = st.sidebar.number_input("Height (Z)", value=3.75, step=0.01, format="%.2f")

st.sidebar.header("2. Items")
default_items = """MEC102A, 7, 3.7, 2.92
MSC137A, 3.6, 3.35, 3.55
MAC105A, 4, 2.8, 0.8"""
items_text = st.sidebar.text_area("List (Name, L, W, H)", value=default_items, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- VISUAL HELPER ---
def get_cube_trace(size, position, color, name="", is_wireframe=False):
    dx, dy, dz = size
    x, y, z = position
    if is_wireframe:
        # Draw Black Container Outline
        x_lines = [x, x+dx, x+dx, x, x,    x, x+dx, x+dx, x, x,    x, x, x+dx, x+dx, x+dx, x+dx]
        y_lines = [y, y, y+dy, y+dy, y,    y, y, y+dy, y+dy, y,    y, y, y, y, y+dy, y+dy]
        z_lines = [z, z, z, z, z,          z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz]
        return go.Scatter3d(x=x_lines, y=y_lines, z=z_lines, mode='lines', line=dict(color='black', width=5), name=name, hoverinfo='name')
    else:
        # Draw Item Mesh
        x_corners = [x, x+dx, x+dx, x,    x, x+dx, x+dx, x]
        y_corners = [y, y,    y+dy, y+dy, y, y,    y+dy, y+dy]
        z_corners = [z, z,    z,    z,    z+dz, z+dz, z+dz, z+dz]
        i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        hover = f"<b>{name}</b><br>Size: {dx:.2f}x{dy:.2f}x{dz:.2f}<br>At: {x:.2f}, {y:.2f}, {z:.2f}"
        return go.Mesh3d(x=x_corners, y=y_corners, z=z_corners, i=i, j=j, k=k, color=color, opacity=1.0, name=name, text=name, hovertemplate=hover, showscale=False)

# --- MAIN LOGIC ---
if run_btn:
    # 1. SETUP
    TOLERANCE = 0.005 # Tolerance for float errors
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
    except: st.stop()

    if not raw_items_data: st.stop()

    # 2. THE STRATEGY
    # We run TWO simulations.
    # Sim A: Standard (Minimizes Height).
    # Sim B: "Width Saver" (We tell the AI that Width is actually Height). 
    #        This forces the AI to stack items sideways (on edge) to keep the "Height" (Real Width) low.
    
    strategies = [
        {'name': 'Standard', 'dims': [cont_l, cont_w, cont_h], 'swap': False},
        {'name': 'Width Saver', 'dims': [cont_l, cont_h, cont_w], 'swap': True} # Swap W and H
    ]
    
    # Try every permutation order (A,B,C), (A,C,B)...
    permutations = list(itertools.permutations(raw_items_data))
    
    best_solution = None
    best_count = -1
    
    progress = st.progress(0)
    total_checks = len(strategies) * len(permutations)
    idx = 0

    for strat in strategies:
        sim_dims = strat['dims']
        
        for order in permutations:
            idx += 1
            if idx % 5 == 0: progress.progress(idx/total_checks)

            packer = Packer()
            # Width in py3dbp is Axis 0 (X), Height is Axis 1 (Y), Depth is Axis 2 (Z)
            # We map Length->X, Width->Y, Height->Z
            packer.add_bin(Bin('SimBin', sim_dims[0], sim_dims[1], sim_dims[2], 9999))
            
            # Create fresh items for this run
            for d in order:
                packer.add_item(Item(d['name'], d['l'], d['w'], d['h'], 1))
            
            packer.pack()
            b = packer.bins[0]
            
            # If we found a better fit
            if len(b.items) > best_count:
                best_count = len(b.items)
                
                # Extract and Map Coordinates back to Reality
                final_items = []
                for item in b.items:
                    d = [float(item.width), float(item.height), float(item.depth)]
                    p = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
                    
                    if strat['swap']:
                        # Simulation: X=L, Y=H, Z=W
                        # Real:       X=L, Y=W, Z=H
                        # Map Sim Y -> Real Z
                        # Map Sim Z -> Real Y
                        real_d = [d[0], d[2], d[1]]
                        real_p = [p[0], p[2], p[1]]
                    else:
                        real_d = d
                        real_p = p
                    
                    final_items.append({'name': item.name, 'dim': real_d, 'pos': real_p})
                
                best_solution = {
                    'items': final_items, 
                    'unfitted': b.unfitted_items,
                    'strategy': strat['name']
                }
            
            if best_count == len(raw_items_data): break
        if best_count == len(raw_items_data): break

    progress.empty()

    # 3. RESULTS
    if best_solution:
        count = len(best_solution['items'])
        c1, c2 = st.columns(2)
        c1.metric("Packed", f"{count} / {len(raw_items_data)}")
        
        if count == len(raw_items_data):
            st.success(f"✅ **Success!** Found a fit using '{best_solution['strategy']}' logic.")
            st.caption("Logic Used: The AI realized it needed to stand items on their edge to save Width.")
        else:
            st.error("❌ Could not fit all items.")
            if best_solution['unfitted']:
                 names = [i.name for i in best_solution['unfitted']]
                 st.write("Unfitted: " + ", ".join(names))

        # 4. PLOT
        fig = go.Figure()
        
        # Container (Black Wireframe)
        fig.add_trace(get_cube_trace([cont_l, cont_w, cont_h], (0,0,0), 'black', "Container", True))
        
        # Items
        colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA']
        for i, dat in enumerate(best_solution['items']):
            # Add tolerance back for visuals
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
            title=f"Result: {count} Items Packed"
        )
        st.plotly_chart(fig, use_container_width=True)
