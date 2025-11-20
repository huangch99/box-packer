import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import itertools

st.set_page_config(page_title="Verifier", layout="wide")
st.title("📦 Final Verification: The L-Shape Layout")

# --- INPUTS ---
cont_l, cont_w, cont_h = 8.25, 6.38, 3.75

raw_items_data = [
    {'name': 'MEC102A', 'l': 7.0, 'w': 3.7, 'h': 2.92},
    {'name': 'MSC137A', 'l': 3.6, 'w': 3.35, 'h': 3.55},
    {'name': 'MAC105A', 'l': 4.0, 'w': 2.8, 'h': 0.8}
]

if st.button("Run Verification", type="primary"):
    # We use the "Width-Saver" logic (Swap Y and Z during calc)
    # This forces the items to stand on edge.
    
    # 1. Setup Simulation (Swapped Dimensions)
    # Sim Width = Real Length (8.25)
    # Sim Height = Real Width (6.38) -> This is what py3dbp tries to minimize (Axis 1)
    # Sim Depth = Real Height (3.75)
    
    # Wait... to force "Width" minimization in py3dbp (which minimizes Height/Axis 1), 
    # we need to map Real Width -> Sim Height.
    sim_dims = [8.25, 3.75, 6.38] # [L, H, W] mapping
    
    # 2. Try Permutations
    permutations = list(itertools.permutations(raw_items_data))
    
    best_bin = None
    
    for order in permutations:
        packer = Packer()
        # Note: 0.005 tolerance subtraction inside Item creation
        packer.add_bin(Bin('SimBin', sim_dims[0], sim_dims[1], sim_dims[2], 9999))
        
        for d in order:
            packer.add_item(Item(d['name'], d['l']-0.005, d['w']-0.005, d['h']-0.005, 1))
            
        packer.pack()
        b = packer.bins[0]
        
        if len(b.items) == 3:
            best_bin = b
            break
            
    if best_bin:
        st.success("✅ All 3 Items Packed Successfully!")
        
        # 3. Display Coordinates (Mapped back to Reality)
        st.subheader("Detailed Coordinate Report")
        
        visual_items = []
        for item in best_bin.items:
            # Sim Dimensions: [L, H, W]
            # Real Dimensions: [L, W, H]
            d = [float(item.width), float(item.height), float(item.depth)]
            p = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
            
            # Map Back: Sim Y -> Real Z, Sim Z -> Real Y
            real_d = [d[0], d[2], d[1]]
            real_p = [p[0], p[2], p[1]]
            
            # Add tolerance back for display
            real_d_disp = [round(x + 0.005, 2) for x in real_d]
            
            st.write(f"**{item.name}**")
            st.write(f"- Size: {real_d_disp}")
            st.write(f"- Position: {real_p}")
            
            visual_items.append({'name': item.name, 'd': real_d_disp, 'p': real_p})
            
        # 4. Plot
        fig = go.Figure()
        
        # Container
        def get_lines(sz, pos):
            dx, dy, dz = sz
            x, y, z = pos
            xl = [x, x+dx, x+dx, x, x, x, x+dx, x+dx, x, x, x, x, x+dx, x+dx, x+dx, x+dx]
            yl = [y, y, y+dy, y+dy, y, y, y, y+dy, y+dy, y, y, y, y, y, y+dy, y+dy]
            zl = [z, z, z, z, z, z+dz, z+dz, z+dz, z+dz, z+dz, z, z+dz, z, z+dz, z, z+dz]
            return xl, yl, zl

        xl, yl, zl = get_lines([8.25, 6.38, 3.75], [0,0,0])
        fig.add_trace(go.Scatter3d(x=xl, y=yl, z=zl, mode='lines', line=dict(color='black', width=5), name='Container'))
        
        colors = ['blue', 'red', 'green']
        for i, v in enumerate(visual_items):
            # Mesh
            x, y, z = v['p']
            dx, dy, dz = v['d']
            fig.add_trace(go.Mesh3d(
                x=[x, x+dx, x+dx, x, x, x+dx, x+dx, x],
                y=[y, y, y+dy, y+dy, y, y, y+dy, y+dy],
                z=[z, z, z, z, z+dz, z+dz, z+dz, z+dz],
                i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
                j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
                k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
                color=colors[i], opacity=1.0, name=v['name']
            ))

        fig.update_layout(scene=dict(
            xaxis=dict(range=[0,8.25], title='L'),
            yaxis=dict(range=[0,6.38], title='W'),
            zaxis=dict(range=[0,3.75], title='H'),
            aspectmode='manual', aspectratio=dict(x=8.25, y=6.38, z=3.75)
        ))
        st.plotly_chart(fig)
        
    else:
        st.error("Failed to pack.")
