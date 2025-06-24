let rangeSlider = function(){
  let slider = $('.range-slider');
  if (slider.length) {
    let range = $('.range-slider__range'),
      value = $('.range-slider__value');

  slider.each(function(){

    value.each(function(){
      let value = $(this).prev().attr('value');
      $(this).html(value);
    });

    range.on('input', function(){
      $(this).next(value).html(this.value);
    });
  });
  }
};

rangeSlider();