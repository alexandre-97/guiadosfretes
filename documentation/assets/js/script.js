//  -----------------------------------------------------------------------------------

//     Template Name: AdminX Admin
//     Template URI: https://phpstack-959325-3347777.cloudwaysapps.com/laadmin/template/landing.html
//     Description: This is Admin theme
//     Author: la-themes
//     Author URI: https://themeforest.net/user/la-themes

// -----------------------------------------------------------------------------------


// 01 Flag  Icon Js
// 02. copy js
// 03. sidebar toggle js
// 04.  List page js
// 05 Sidebar scroll js
// 06. Loader JS
// 07. tap on top
// 08. flag dropdown
// 09. hide-show
// 10. dark mode js
// 11 close on click js
// 12 change title




// >>-- 01 Flag  Icon Js --<<
// Horizontal Nav css
let navBar = $(".main-nav");
let size = "150px";
let leftsideLimit = -100;
let navbarSize;
let containerWidth;
let maxNavbarLimit;

function setUpHorizontalHeader() {
  navbarSize = navBar.width();
  containerWidth = ($(".simplebar-content").width())
  maxNavbarLimit = -(navbarSize - containerWidth);
  if ($("nav").hasClass("horizontal-sidebar")) {
    $(".menu-next").removeClass("d-none");
    $(".menu-previous").removeClass("d-none");
  } else {
    navBar.css("marginLeft",0)
    $(".menu-next").addClass("d-none");
    $(".menu-previous").addClass("d-none");
  }
  $(".horizontal-sidebar .show").removeClass("show");
}

$(document).on('click', '.menu-previous', function (e) {
  let layoutOption = getLocalStorageItem("layout-option","ltr");
  let attribute = layoutOption == 'ltr' ? 'marginLeft' : 'marginRight';
  let currentPosition = parseInt(navBar.css(attribute));
  if (currentPosition < 0) {
    navBar.css(`${attribute}`, "+=" + size)
    $(".menu-next").removeClass("d-none");
    $(".menu-previous").removeClass("d-none");
    if (currentPosition >= leftsideLimit) {
      $(this).addClass("d-none");
    }
  }
})


$(document).on('click', '.menu-next', function (e) {
  let layoutOption = getLocalStorageItem("layout-option","ltr");
  let attribute = layoutOption == 'ltr' ? 'marginLeft' : 'marginRight';
  let currentPosition = parseInt(navBar.css(attribute));
  if (currentPosition >= maxNavbarLimit) {
    $(".menu-next").removeClass("d-none");
    $(".menu-previous").removeClass("d-none");
    navBar.css(`${attribute}`, "-=" + size)
    if (currentPosition - parseInt(size) <= maxNavbarLimit) {
      $(this).addClass("d-none");
    }
  }
})


$(function () {
  setUpHorizontalHeader();
  console.log("Loading");
  let themeMode = getLocalStorageItem('theme-mode', 'light')
  setTimeout(() => {
    $('body').addClass(`${themeMode}`)
  }, 1000);
});


//  **------flag dropdown**
$(function () {
  var text = $(".selected i").attr('class')
  $(".flag i").prop('class', text);
  $(document).on('click', '.lang', function () {
    $(".lang").removeClass("selected");
    $(this).addClass("selected");
    text = $(".selected i").attr('class')
    $(".flag i").prop('class', text);
  });
})



// >>-- 02 copy Js --<<
function copyvalue() {
  var temp = document.createElement('input');
  var texttoCopy = document.getElementById('copyText2').innerHTML;
  temp.type = 'input';
  temp.setAttribute('value', texttoCopy);
  document.body.appendChild(temp);
  temp.select();
  document.execCommand("copy");
  temp.remove();
  console.timeEnd('time2');
}



// >>-- 03 sidebar toggle js --<<
$(document).on('click', '.header-toggle', function () {
  $("nav").toggleClass("semi-nav");
});
$(".toggle-semi-nav").on("click", function () {
  $("nav").removeClass("semi-nav");
});


// >>-- 04 List page js --<<
$(".contact-listbox").on("click", function () {
  $(this).toggleClass("stared");
});

function resize() {
  var $window = $(window),
    $nav = $('nav');

  $nav.removeClass('semi-nav');
  if ($window.width() < 768) {
    // $nav.removeClass('semi-nav');

  } else if ($window.width() < 1199) {
    $nav.addClass('semi-nav');
  }
}

$(function () {
  resize();
});
window.addEventListener("resize", () => {
  resize();
});


// >>-- 05 Sidebar scroll js --<<
var myElement = document.getElementById('app-simple-bar');
new SimpleBar(myElement, { autoHide: true });



// Sidebar active class js
$(function () {
  let current = location.pathname;
  current = current.substring((current.lastIndexOf('/')) + 1);
  $('.main-nav li a').each(function () {
    var $this = $(this);
    if (current === $this.attr("href").split('/').pop()) {
      if ($this.parent().parent().parent().hasClass("another-level")) {
        $this.parent().parent().parent().parent().closest('li').children().addClass('show').attr("aria-expanded", "true");
      }
      $this.parent().parent().parent().children().addClass('show');
      $this.parent().parent().parent().children().attr("aria-expanded", "true");
      $this.parent('li').addClass('active');
    }
  })
})



// >>-- 06 Loader JS --<<
$('.loader-wrapper').fadeOut('slow', function () {
  $(this).remove();
});




// >>-- 07 tap on top --<<
let calcScrollValue = () => {
  let scrollProgress = document.getElementsByClassName("go-top");
  let progressValue = document.getElementsByClassName("progress-value");
  let pos = document.documentElement.scrollTop;
  let calcHeight =
    document.documentElement.scrollHeight -
    document.documentElement.clientHeight;
  let scrollValue = Math.round((pos * 100) / calcHeight);
  if (pos > 100) {
    scrollProgress[0].style.display = 'grid';
  } else {
    scrollProgress[0].style.display = 'none';
  }

  scrollProgress[0].addEventListener("click", () => {
    document.documentElement.scrollTop = 0;
  });

  scrollProgress[0].style.background = `conic-gradient( rgba(var(--primary),1) ${scrollValue}%, var(--light-gray) ${scrollValue}%)`;
};

window.onscroll = calcScrollValue;



// >>-- 08 flag dropdown --<<
$(function () {
  var text = $(".selected img").attr('src')
  $(".flag img").prop('src', text);
  $(document).on('click', '.lang', function () {
    $(".lang").removeClass("selected");
    $(this).addClass("selected");
    text = $(".selected img").attr('src')
    $(".flag img").prop('src', text);
  });
})
$(function () {
  var text = $(".selected i").attr('class')
  $(".flag i").prop('class', text);
  $(document).on('click', '.lang', function () {
    $(".lang").removeClass("selected");
    $(this).addClass("selected");
    text = $(".selected i").attr('class')
    $(".flag i").prop('class', text);
  });
})


// >>-- 09 hide-show --<<

function myFunction() {
  var x = document.getElementById("myapp");
  if (x.style.display === "none") {
    x.style.display = "block";
    let buttoncontent = $("#button-content").html().replace(/</g, "&lt;").replace(/>/g, "&gt;");
    $("#button-code").html(buttoncontent)
  } else {
    x.style.display = "none";
    $("#button-code").html("")
  }
}


// >>-- 10 dark mode js --<<

document.querySelector(".header-dark").addEventListener("click", () => {
  document.querySelector(".sun-logo").classList.toggle("sun");
  document.querySelector(".moon-logo").classList.toggle("moon");
  if ($('body').hasClass("dark")) {
    document.body.classList.remove("dark")
    document.body.classList.add("light")
    setLocalStorageItem('theme-mode', 'light')
  } else {
    document.body.classList.remove("light")
    document.body.classList.add("dark")
    setLocalStorageItem('theme-mode', 'dark')
  }
})
function appendHtml() {
  var div = document.getElementsByClassName('app-wrapper');
  div.innerHTML += '<p>This is some HTML code</p>';
}
window.onload = function () {
  appendHtml();
}


// >>-- 11 close on click js --<<

$(document).on('click', '.close-btn', function () {
  let targetItem = $(this).closest(".head-box");
  let targetParent = targetItem.parent();
  $(this).parent().parent().remove();
  if (targetParent.find(".head-box").length <= 0) {
    targetParent.parent().parent().find('.card-footer').addClass('d-none');
  }
});

// // 



var closeCollaps = document.querySelectorAll('.main-nav li a[data-bs-toggle="collapse"]');
closeCollaps.forEach(function (element) {
  element.addEventListener('click', function () {
    var parent = element.closest('.collapse');
    var all = document.querySelectorAll('.collapse');
    all.forEach(function (e) {
      if (e !== parent) {
        e.classList.remove('show');
        var ariaexpand = e.previousElementSibling;
        if (ariaexpand) ariaexpand.setAttribute('aria-expanded', 'false');
      }
    });
    parent?.classList.add('show');
    var ariaexpand = element;
    if (ariaexpand) ariaexpand.setAttribute('aria-expanded', 'true');
  });
});

// >>-- 12 change title --<<
const title = document.title;
window.addEventListener('focus', function() {
  document.title = title;
}.bind(window));

window.addEventListener('blur', function() {
  document.title = "👋🏻 Come Back...";
}.bind(window));