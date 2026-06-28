document.addEventListener("DOMContentLoaded", function () {

    document.querySelectorAll(".card h1").forEach(function(el){

        let end = parseInt(el.innerText);

        if (isNaN(end)) return;

        let n = 0;

        let timer = setInterval(function(){

            n++;

            el.innerText = n;

            if(n >= end){
                el.innerText = end;
                clearInterval(timer);
            }

        },25);

    });

});
