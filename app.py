import streamlit as st
import plotly.graph_objects as go
from py3dbp import Packer, Bin, Item
import decimal

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Multi-Item Box Visualizer", layout="wide")
st.title("📦 Multi-Item Shipping Calculator")
st.markdown("**Logic:** Uses the `py3dbp` algorithm. Items that **do not fit** will be stacked outside the box for visual comparison.")

# --- SESSION STATE INITIALIZATION ---
if 'items_to_pack' not in st.session_state:
    st.session_state.items_to_pack = []

# --- SIDEBAR: CONFIGURATION ---
st.sidebar.header("1. Define Box (Inner Dims)")
box_l = st.sidebar.number_input("Box Length", value=12.0)
box_w = st.sidebar.number_input("Box Width", value=12.0)
box_h = st.sidebar.number_input("Box Height", value=12.0)
# Internally set weight to infinity
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

# --- HELPER: ANALYZE FAILURE REASON ---
def analyze_failure(bin_obj, item_obj):
    """
    Determines why an item failed to pack based on geometry only.
    """
    # 1. Check Dimensions
    bin_dims = sorted([float(bin_obj.width), float(bin_obj.height), float(bin_obj.depth)])
    item_dims = sorted([float(item_obj.width), float(item_obj.height), float(item_obj.depth)])
    
    if any(i > b for i, b in zip(item_dims, bin_dims)):
        return "❌ Item is too large for box (Dimensions mismatch)"

    # 2. Space (Since weight is ignored)
    return "📦 Not enough remaining space (or fragmentation)"

# --- CALCULATION LOGIC ---
if st.button("Calculate Packing", type="primary"):
    if not st.session_state.items_to_pack:
        st.warning("Please add items first.")
    else:
        packer = Packer()
        # We set max weight to a huge number so it is effectively ignored
        IGNORED_WEIGHT_LIMIT = 999999999 
        packer.add_bin(Bin('MainBox', box_l, box_w, box_h, IGNORED_WEIGHT_LIMIT))

        for i, item in enumerate(st.session_state.items_to_pack):
            # We give every item a dummy weight of 1.
            p_item = Item(f"{item['name']}-{i}", item['l'], item['w'], item['h'], 1)
            p_item.color = item['color'] 
            packer.add_item(p_item)

        packer.pack()

        box = packer.bins[0]
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.subheader("Results")
            
            # Stats
            total_volume = box_l * box_w * box_h
            used_volume = float(box.get_volume())
            efficiency = (used_volume / total_volume) * 100
            
            st.metric("Packed Items", len(box.items))
            st.metric("Volume Utilization", f"{efficiency:.1f}%")

            # Success Check
            if len(box.unfitted_items) == 0:
                st.success("✅ All items fit!")
            else:
                st.error(f"❌ {len(box.unfitted_items)} items did NOT fit.")
                st.info("Unfitted items are shown OUTSIDE the box.")
                st.markdown("### Failed Items Analysis:")
                
                for item in box.unfitted_items:
                    reason = analyze_failure(box, item)
                    with st.expander(f"{item.name} (Failed)", expanded=True):
                        st.write(f"**Reason:** {reason}")
                        st.caption(f"Dims: {float(item.width)}x{float(item.height)}x{float(item.depth)}")

        with col2:
            # Calculate plot limits to include external items
            max_x_draw = box_l
            
            fig = go.Figure()
            
            # 1. Draw Container Wireframe
            fig.add_trace(get_wireframe(box_l, box_w, box_h))
            
            # 2. Draw Packed Items (Fitted)
            for item in box.items:
                x, y, z = float(item.position[0]), float(item.position[1]), float(item.position[2])
                w, h, d = float(item.get_dimension()[0]), float(item.get_dimension()[1]), float(item.get_dimension()[2])
                color = getattr(item, 'color', 'gray')
                fig.add_trace(get_cube_trace(x, y, z, w, h, d, color, item.name))

            # 3. Draw Unfitted Items (Outside the box)
            if len(box.unfitted_items) > 0:
                # Start stacking them to the right of the box with a small gap
                gap = box_l * 0.1
                start_x = box_l + gap
                current_z = 0
                
                for item in box.unfitted_items:
                    # We use original dims because rotation wasn't calculated for unfitted items
                    w, h, d = float(item.width), float(item.height), float(item.depth)
                    
                    # Draw trace
                    color = getattr(item, 'color', 'red')
                    fig.add_trace(get_cube_trace(start_x, 0, current_z, w, h, d, color, f"FAILED: {item.name}", opacity=0.5))
                    
                    # Stack upwards
                    current_z += d
                    # Update max X for camera scaling
                    if (start_x + w) > max_x_draw:
                        max_x_draw = start_x + w

                # Add a label for the overflow stack
                fig.add_trace(go.Scatter3d(
                    x=[start_x], y=[0], z=[current_z + 1],
                    mode='text', text=['Did Not Fit'],
                    textfont=dict(color='red', size=12)
                ))

            # Update Layout for Aspect Ratio
            layout = go.Layout(
                scene=dict(
                    xaxis=dict(title='Length (x)', range=[0, max_x_draw * 1.1]),
                    yaxis=dict(title='Width (y)', range=[0, max(box_w, box_l)]), # Keep proportional
                    zaxis=dict(title='Height (z)', range=[0, max(box_h, box_l)]),
                    aspectmode='data' # This forces 1 unit = 1 unit visually
                ),
                margin=dict(l=0, r=0, b=0, t=0),
                height=600
            )
            
            fig.update_layout(layout)
            st.plotly_chart(fig, use_container_width=True)
