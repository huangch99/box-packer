import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import decimal

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Multi-Item Box Visualizer", layout="wide")
st.title("📦 Multi-Item Shipping Calculator")
st.markdown("**Logic:** Items are automatically sorted by **Volume (Largest to Smallest)** before packing.")

# --- SESSION STATE INITIALIZATION ---
if 'items_to_pack' not in st.session_state:
    st.session_state.items_to_pack = []

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("1. Define Box (Inner Dims)")
box_l = st.sidebar.number_input("Box Length", value=12.0)
box_w = st.sidebar.number_input("Box Width", value=12.0)
box_h = st.sidebar.number_input("Box Height", value=12.0)
st.sidebar.caption("Weight capacity is disabled (Calculates by Size only)")

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

if st.sidebar.button("Clear Entire List"):
    st.session_state.items_to_pack = []

# --- MAIN PANEL: ITEM LIST ---
st.subheader(f"Current Item List ({len(st.session_state.items_to_pack)} items)")

if len(st.session_state.items_to_pack) > 0:
    # Create a header row
    h1, h2, h3, h4, h5 = st.columns([1, 3, 2, 1, 1])
    h1.markdown("**No.**")
    h2.markdown("**Name**")
    h3.markdown("**Dims (LxWxH)**")
    h4.markdown("**Color**")
    h5.markdown("**Remove**")
    
    st.markdown("---")

    # Loop through items and display them with a delete button
    # We enumerate so we have the index 'i' to delete the specific item
    for i, item in enumerate(st.session_state.items_to_pack):
        c1, c2, c3, c4, c5 = st.columns([1, 3, 2, 1, 1])
        
        with c1:
            st.write(f"#{i+1}")
        with c2:
            st.write(item['name'])
        with c3:
            st.write(f"{item['l']} x {item['w']} x {item['h']}")
        with c4:
            # Show a small color block
            st.color_picker("", item['color'], disabled=True, label_visibility="collapsed", key=f"col_{i}")
        with c5:
            # The Delete Button
            if st.button("🗑️", key=f"remove_{i}"):
                st.session_state.items_to_pack.pop(i)
                st.rerun() # Immediately refresh the app to show the item is gone
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

# --- HELPER: ANALYZE FAILURE REASON ---
def analyze_failure(bin_obj, item_obj):
    bin_dims = sorted([float(bin_obj.width), float(bin_obj.height), float(bin_obj.depth)])
    item_dims = sorted([float(item_obj.width), float(item_obj.height), float(item_obj.depth)])
    
    if any(i > b for i, b in zip(item_dims, bin_dims)):
        return "❌ Item is too large for box (Dimensions mismatch)"
    return "📦 Not enough remaining space (or fragmentation)"

# --- CALCULATION LOGIC ---
if st.button("Calculate Packing (Largest First)", type="primary"):
    if not st.session_state.items_to_pack:
        st.warning("Please add items first.")
    else:
        # --- STEP 1: SORT ITEMS BY VOLUME (DESCENDING) ---
        sorted_items = sorted(
            st.session_state.items_to_pack, 
            key=lambda x: x['l'] * x['w'] * x['h'], 
            reverse=True
        )
        
        packer = Packer()
        IGNORED_WEIGHT_LIMIT = 999999999 
        packer.add_bin(Bin('MainBox', box_l, box_w, box_h, IGNORED_WEIGHT_LIMIT))

        for i, item in enumerate(sorted_items):
            p_item = Item(f"{item['name']}-{i}", item['l'], item['w'], item['h'], 1)
            p_item.color = item['color'] 
            packer.add_item(p_item)

        packer.pack()
        box = packer.bins[0]
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.subheader("Results")
            
            total_volume = box_l * box_w * box_h
            used_volume = float(box.get_volume())
            efficiency = (used_volume / total_volume) * 100
            
            st.metric("Packed Items", len(box.items))
            st.metric("Volume Utilization", f"{efficiency:.1f}%")

            if len(box.unfitted_items) == 0:
                st.success("✅ All items fit!")
            else:
                st.error(f"❌ {len(box.unfitted_items)} items did NOT fit.")
                st.info("Items processed Largest -> Smallest.")
                
                for item in box.unfitted_items:
                    reason = analyze_failure(box, item)
                    with st.expander(f"{item.name} (Failed)", expanded=True):
                        st.write(f"**Reason:** {reason}")
                        st.caption(f"Dims: {float(item.width)}x{float(item.height)}x{float(item.depth)}")

        with col2:
            max_x_draw = box_l
            fig = go.Figure()
            
            # Draw Wireframe
            fig.add_trace(get_wireframe(box_l, box_w, box_h))
            
            # Draw Packed Items
            for item in box.items:
                x, y, z = float(item.position[0]), float(item.position[1]), float(item.position[2])
                w, h, d = float(item.get_dimension()[0]), float(item.get_dimension()[1]), float(item.get_dimension()[2])
                color = getattr(item, 'color', 'gray')
                fig.add_trace(get_cube_trace(x, y, z, w, h, d, color, item.name))

            # Draw Unfitted Items
            if len(box.unfitted_items) > 0:
                gap = box_l * 0.1
                start_x = box_l + gap
                current_z = 0
                
                for item in box.unfitted_items:
                    w, h, d = float(item.width), float(item.height), float(item.depth)
                    color = getattr(item, 'color', 'red')
                    fig.add_trace(get_cube_trace(start_x, 0, current_z, w, h, d, color, f"FAILED: {item.name}", opacity=0.5))
                    
                    current_z += d
                    if (start_x + w) > max_x_draw:
                        max_x_draw = start_x + w

                fig.add_trace(go.Scatter3d(
                    x=[start_x], y=[0], z=[current_z + 1],
                    mode='text', text=['Did Not Fit'],
                    textfont=dict(color='red', size=12)
                ))

            layout = go.Layout(
                scene=dict(
                    xaxis=dict(title='Length (x)', range=[0, max_x_draw * 1.1]),
                    yaxis=dict(title='Width (y)', range=[0, max(box_w, box_l)]),
                    zaxis=dict(title='Height (z)', range=[0, max(box_h, box_l)]),
                    aspectmode='data'
                ),
                margin=dict(l=0, r=0, b=0, t=0),
                height=600
            )
            
            fig.update_layout(layout)
            st.plotly_chart(fig, use_container_width=True)
