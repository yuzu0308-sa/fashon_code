from flask import Flask, render_template, jsonify, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
import os
import pandas as pd
import io
from flask import send_file

# --- アプリケーションの初期設定 ---
basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key' # CSRF対策やセッション管理のための秘密鍵
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- ログインマネージャーの設定 ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login' # 未ログイン時にリダイレクトする先
login_manager.login_message = "このページにアクセスするにはログインが必要です。"

# --- データベースモデルの定義 ---

# Userモデル (管理者用)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Productモデル (商品)
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_filename = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Integer, nullable=False) # 価格を追加
    likes = db.Column(db.Integer, default=0)

# Orderモデル (注文情報)
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    # 注文詳細との関連付け
    details = db.relationship('OrderDetail', backref='order', lazy=True)

# OrderDetailモデル (注文の詳細)
class OrderDetail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    # 商品情報との関連付け
    product = db.relationship('Product', backref='order_details', lazy=True)

# --- ログインユーザーの読み込み ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 一般ユーザー向けルート ---

@app.route('/')
@app.route('/<category>')
def index(category=None):
    search_query = request.args.get('q')
    products_query = Product.query

    if category:
        products_query = products_query.filter_by(category=category)
    
    if search_query:
        products_query = products_query.filter(Product.name.ilike(f'%{search_query}%'))
    
    products = products_query.all()
    
    return render_template('index.html', products=products, category=category, search_query=search_query)

@app.route('/like/<int:product_id>', methods=['POST'])
def like(product_id):
    product = Product.query.get_or_404(product_id)
    product.likes += 1
    db.session.commit()
    return jsonify({'success': True, 'likes': product.likes})

# --- カート機能のルート ---

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = {}
    
    cart = session['cart']
    product_id_str = str(product_id)

    cart[product_id_str] = cart.get(product_id_str, 0) + 1
    
    session.modified = True
    flash(f'商品をカートに追加しました！', 'success')
    return redirect(request.referrer or url_for('index'))

@app.route('/cart')
def view_cart():
    if 'cart' not in session or not session['cart']:
        return render_template('cart.html', cart_items=[], total_price=0)

    cart_product_ids = [int(pid) for pid in session['cart'].keys()]
    products_in_cart = Product.query.filter(Product.id.in_(cart_product_ids)).all()
    
    cart_items = []
    total_price = 0
    for product in products_in_cart:
        quantity = session['cart'][str(product.id)]
        item_total = product.price * quantity
        cart_items.append({
            'product': product,
            'quantity': quantity,
            'item_total': item_total
        })
        total_price += item_total
        
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    product_id_str = str(product_id)
    if 'cart' in session and product_id_str in session['cart']:
        session['cart'].pop(product_id_str)
        session.modified = True
        flash('商品をカートから削除しました。', 'info')
    return redirect(url_for('view_cart'))

# --- 購入プロセスのルート ---

@app.route('/checkout', methods=['POST'])
def checkout():
    if 'cart' not in session or not session['cart']:
        flash('カートが空です。', 'danger')
        return redirect(url_for('view_cart'))

    new_order = Order()
    db.session.add(new_order)
    db.session.commit()

    for product_id_str, quantity in session['cart'].items():
        product_id = int(product_id_str)
        order_detail = OrderDetail(
            order_id=new_order.id,
            product_id=product_id,
            quantity=quantity
        )
        db.session.add(order_detail)

    db.session.commit()

    session.pop('cart', None)

    flash('ご購入ありがとうございました！', 'success')
    return redirect(url_for('index'))

# --- 管理者向けルート ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('ユーザー名またはパスワードが正しくありません。', 'danger')

    return render_template('admin_login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    # 売上統計データを集計
    sales_stats = db.session.query(
        Product.name,
        func.sum(OrderDetail.quantity).label('total_sold')
    ).join(OrderDetail, Product.id == OrderDetail.product_id)\
     .group_by(Product.name)\
     .order_by(func.sum(OrderDetail.quantity).desc())\
     .all()

    # ✨ --- ここからが追加する部分です --- ✨
    # いいねランキングデータを集計
    likes_stats = Product.query.order_by(Product.likes.desc()).all()
    # ✨ --- ここまで追加 --- ✨

    # 戻り値に likes_stats を追加します
    return render_template('admin_dashboard.html', sales_stats=sales_stats, likes_stats=likes_stats)


# --- データベースの初期化と初期データ投入 ---
with app.app_context():
    db.create_all()
    if Product.query.count() == 0:
        sample_products = [
            Product(name='パステルカラーTシャツ', category='mens', image_filename='fashion_shirt1_white.png', price=3500),
            Product(name='ボーダー柄ロングTシャツ', category='mens', image_filename='mens_jacket.jpg', price=4200),
            Product(name='フリル付きブラウス', category='ladies', image_filename='ladies_blouse.jpg', price=5800),
            Product(name='チェック柄プリーツスカート', category='ladies', image_filename='fashion_onepiece.png', price=6500),
            Product(name='リラックスフィットシャツ', category='mens', image_filename='mens_shirt.png', price=4800),
            Product(name='花柄ワンピース', category='ladies', image_filename='ladies_onepiece.png', price=8800),
        ]
        db.session.bulk_save_objects(sample_products)
        db.session.commit()

    if User.query.count() == 0:
        admin = User(username='admin')
        admin.set_password('password')
        db.session.add(admin)
        db.session.commit()
        print("Admin user created with username: admin, password: password")

@app.route('/admin/dashboard/download_excel')
@login_required
def download_excel():
    # 1. データベースから全商品の統計データを取得
    # outerjoinを使い、売上がない商品も取得対象に含める
    sales_stats = db.session.query(
        Product.name,
        Product.likes,
        # 売上がない場合(NULL)は0として表示する
        func.coalesce(func.sum(OrderDetail.quantity), 0).label('total_sold')
    ).outerjoin(OrderDetail, Product.id == OrderDetail.product_id) \
     .group_by(Product.id) \
     .order_by(Product.name) \
     .all()

    # 2. pandasのDataFrameに変換 (カラムの順番をクエリに合わせる)
    df = pd.DataFrame(sales_stats, columns=['商品名', 'いいね数', '販売数'])

    # 3. エクセルファイルデータをメモリ上に作成
    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name='商品統計')
    output.seek(0)

    # 4. ファイルとしてユーザーに送信
    return send_file(
        output,
        as_attachment=True,
        download_name='product_stats.xlsx', # ファイル名をより分かりやすく変更
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
# --- アプリケーションの実行 ---
if __name__ == '__main__':
    app.run(debug=True)