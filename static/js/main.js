document.addEventListener('DOMContentLoaded', function() {
    // クラス名が 'like-button' のボタンを全て取得
    const likeButtons = document.querySelectorAll('.like-button');
    
    likeButtons.forEach(button => {
        button.addEventListener('click', function() {
            // ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
            // ここを修正しました！
            // 'data-product-id'属性を取得するため、'.dataset.productId'を使います
            const productId = this.dataset.productId;
            // ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲

            // productIdが取得できない場合は処理を中断
            if (!productId) {
                console.error('Product ID not found on the button.');
                return;
            }

            const url = `/like/${productId}`;

            // fetch APIを使って非同期でサーバーにリクエストを送信
            fetch(url, {
                method: 'POST',
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json(); // レスポンスをJSON形式に変換
            })
            .then(data => {
                // 成功した場合の処理
                if (data.success) {
                    // 対応するいいね数の表示を更新
                    const countElement = document.getElementById(`like-count-${productId}`);
                    if (countElement) {
                        countElement.textContent = data.likes;
                    }
                }
            })
            .catch(error => {
                // エラーが発生した場合、コンソールに表示
                console.error('There was a problem with the fetch operation:', error);
            });
        });
    });
});