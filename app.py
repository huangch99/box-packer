import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- PAGE SETUP ---
st.set_page_config(page_title="3D Box Packer", layout="wide")
st.title("📦 3D Packing Simulator")

# --- SIDEBAR: INPUTS ---
st.sidebar.header("1. Define Box Size")
bin_w = st.sidebar.number_input("Bin Width", value=50, step=1)
bin_h = st.sidebar.number_input("Bin Height", value=50, step=1)
bin_d = st.sidebar.number_input("Bin Depth", value=50, step=1)

st.sidebar.header("2. Define Items")
st.sidebar.write("Enter items below (Name, Width, Height, Depth). One per line.")

# Default data to show user how it works
default_data = """Laptop, 30, 2, 20
ShoeBox, 20, 10, 30
Cube, 15, 15, 15
Tube, 5, 5, 45"""

# Text Area is easier than clicking buttons multiple times
items_text = st.sidebar.text_area("Item List", value=default_data, height=200)
run_btn = st.sidebar.button("Pack Items", type="primary")

# --- HELPER FUNCTIONS ---
def get_cube_mesh(size, position, color, opacity=1.0, name=""):
    dx, dy, dz = size
    x, y, z = position
    x_coords = [x, x+dx, x+dx, x,    x, x+dx, x+dx, x]
    y_coords = [y, y,    y+dy, y+dy, y, y,    y+dy, y+dy]
    z_coords = [z, z,    z,    z,    z+dz, z+dz, z+dz, z+dz]
    i = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
    j = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
    k = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
    return go.Mesh3d(x=x_coords, y=y_coords, z=z_coords, i=i, j=j, k=k, color=color, opacity=opacity, name=name, showscale=False, hoverinfo='name')

# --- MAIN LOGIC ---
if run_btn:
    # 1. Parse the text input
    item_obj_list = []
    try:
        lines = items_text.strip().split('\n')
        for line in lines:
            parts = line.split(',')
            if len(parts) >= 4:
                name = parts[0].strip()
                w = float(parts[1].strip())
                h = float(parts[2].strip())
                d = float(parts[3].strip())
                item_obj_list.append(Item(name, w, h, d, 1)) # Weight is set to 1 for visualization
    except Exception as e:
        st.error(f"Error reading list: {e}. Please check your formatting.")
        st.stop()

    # 2. Run the Packing Algorithm
    packer = Packer()
    packer.add_bin(Bin('MainBin', bin_w, bin_h, bin_d, 10000)) # Large weight limit
    for item in item_obj_list:
        packer.add_item(item)
    
    packer.pack()
    b_result = packer.bins[0]

    # 3. Display Stats
    c1, c2, c3 = st.columns(3)
    c1.metric("Items Packed", f"{len(b_result.items)} / {len(item_obj_list)}")
    c2.metric("Unfitted Items", len(b_result.unfitted_items))
    
    # 4. Draw 3D Chart
    fig = go.Figure()
    # Bin (Transparent)
    fig.add_trace(get_cube_mesh([bin_w, bin_h, bin_d], (0,0,0), 'grey', 0.1, 'Bin'))
    
    # Items
    colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A']
    if len(b_result.items) > 0:
        for idx, item in enumerate(b_result.items):
            dims = [float(item.width), float(item.height), float(item.depth)]
            pos = [float(item.position[0]), float(item.position[1]), float(item.position[2])]
            fig.add_trace(get_cube_mesh(dims, pos, colors[idx % 5], 1.0, item.name))
    else:
        st.warning("No items fit in the box!")

    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[0, bin_w], title='Width'),
            yaxis=dict(range=[0, bin_h], title='Height'),
            zaxis=dict(range=[0, bin_d], title='Depth'),
            aspectmode='data'
        ),
        height=700,
        margin=dict(l=0, r=0, b=0, t=0)
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # 5. List items that didn't fit
    if len(b_result.unfitted_items) > 0:
        st.error("❌ These items were too big to fit:")
        for item in b_result.unfitted_items:
            st.write(f"- {item.name}")

else:
    st.info("👈 Change settings in the sidebar and click 'Pack Items'")
