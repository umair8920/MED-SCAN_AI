$(document).ready(function () {
$(".Navigation-btn").click(function () { 
    $(this).siblings('ul').slideToggle();
    $(this).children('.arrow-icon').toggleClass("rotate");
     $(this).toggleClass("Navigation-active");
});
});

function NavHide() {
    $("#side-bar").toggleClass("Sidenavhide");
    $(".page-wrapper").toggleClass("content-gap");
  }