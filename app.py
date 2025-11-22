import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Multi-Item Box Visualizer", layout="wide")
st.title("📦 Multi-Item Shipping Calculator")
st.markdown("**Logic:** Uses the `py3dbp` algorithm to stack multiple items (Tetris-style) into a single box.")

# --- SESSION STATE INITIALIZATION ---
if 'items_to_pack' not in st.session_state:
    st.session_state.items_to_pack = []

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("1. Define Box (Inner Dims)")
box_l = st.sidebar.number_input("Box Length", value=12.0)
box_w = st.sidebar.number_input("Box Width", value=12.0)
box_h = st.sidebar.number_input("Box Height", value=12.0)
max_weight = st.sidebar.number_input("Max Weight Capacity", value=50.0)

st.sidebar.markdown("---")
st.sidebar.header("2. Add Items")
item_name = st.sidebar.text_input("Item Name", value="Product A")
c1, c2, c3 = st.sidebar.columns(3)
i_l = c1.number_input("L", value=5.0)
i_w = c2.number_input("W", value=5.0)
i_h = c3.number_input("H", value=5.0)
i_qty = st.sidebar.number_input("Qty", value=1, min_value=1)
i_color = st.sidebar.color_picker("Color", "#00CC96")

if st.sidebar.button("Add Item to List"):
    for _ in range(int(i_qty)):
        st.session_state.items_to_pack.append({
            "name": item_name,
            "l": i_l, "w": i_w, "h": i_h,
            "color": i_color
        })
    st.success(f"Added {i_qty} x {item_name}")

if st.sidebar.button("Clear List"):
    st.session_state.items_to_pack = []

# --- MAIN PANEL: ITEM LIST ---
st.subheader(f"Current Item List ({len(st.session_state.items_to_pack)} items)")
if len(st.session_state.items_to_pack) > 0:
    st.dataframe(st.session_state.items_to_pack)
else:
    st.info("Add items from the sidebar to start.")

# --- VISUALIZATION FUNCTIONS ---
def get_cube_trace(x, y, z, l, w, h, color, name, opacity=1.0):
    x_pts = [x, x+l, x+l, x, x, x+l, x+l, x]
    y_pts = [y, y, y+w, y+w, y, y, y+w, y+w]
    z_pts = [z, z, z, z, z+h, z+h, z+h, z+h]

    return go.Mesh3d(
        x=x_pts, y=y_pts, z=z_pts,
        i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
        j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
        k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
        opacity=opacity,
        color=color,
        name=name,
        showscale=False,
        hoverinfo='name'
    )

def get_wireframe(l, w, h):
    pts = [
        (0,0,0), (l,0,0), (l,w,0), (0,w,0), (0,0,0),
        (0,0,h), (l,0,h), (l,w,h), (0,w,h), (0,0,h),
        (0,0,h), (0,0,0), (l,0,0), (l,0,h),
        (l,w,h), (l,w,0), (0,w,0), (0,w,h)
    ]
    X = [p[0] for p in pts]
    Y = [p[1] for p in pts]
    Z = [p[2] for p in pts]
    return go.Scatter3d(x=X, y=Y, z=Z, mode='lines', line=dict(color='black', width=4), name='Bin Frame')

# --- CALCULATION LOGIC ---
if st.button("Calculate Packing", type="primary"):
    if not st.session_state.items_to_pack:
        st.warning("Please add items first.")
    else:
        packer = Packer()
        packer.add_bin(Bin('MainBox', box_l, box_w, box_h, max_weight))

        for i, item in enumerate(st.session_state.items_to_pack):
            p_item = Item(f"{item['name']}-{i}", item['l'], item['w'], item['h'], 1)
            p_item.color = item['color'] 
            packer.add_item(p_item)

        packer.pack()

        box = packer.bins[0]
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.subheader("Results")
            if len(box.unfitted_items) == 0:
                st.success("✅ All items fit!")
            else:
                st.error(f"❌ {len(box.unfitted_items)} items did NOT fit.")
            
            st.metric("Packed Items", len(box.items))
            
            # --- FIX START: Convert Decimal to Float ---
            total_volume = box_l * box_w * box_h
            used_volume = float(box.get_volume()) # Converted to float here
            efficiency = (used_volume / total_volume) * 100
            st.metric("Volume Utilization", f"{efficiency:.1f}%")
            # --- FIX END ---
            
            if box.unfitted_items:
                st.warning("Items left behind:")
                for item in box.unfitted_items:
                    st.write(f"- {item.name}")

        with col2:
            layout = go.Layout(
                scene=dict(
                    xaxis=dict(title='Length (x)', range=[0, box_l]),
                    yaxis=dict(title='Width (y)', range=[0, box_w]),
                    zaxis=dict(title='Height (z)', range=[0, box_h]),
                    aspectmode='manual',
                    aspectratio=dict(x=1, y=box_w/box_l, z=box_h/box_l)
                ),
                margin=dict(l=0, r=0, b=0, t=0),
                height=600
            )
            
            fig = go.Figure(layout=layout)
            fig.add_trace(get_wireframe(box_l, box_w, box_h))
            
            for item in box.items:
                x, y, z = float(item.position[0]), float(item.position[1]), float(item.position[2])
                w, h, d = float(item.get_dimension()[0]), float(item.get_dimension()[1]), float(item.get_dimension()[2])
                color = getattr(item, 'color', 'gray')
                fig.add_trace(get_cube_trace(x, y, z, w, h, d, color, item.name))

            st.plotly_chart(fig, use_container_width=True)
