var model = {
    shutters: [],
};
for (var s=0; s < 1; s+=.04) {
    var micro = Math.floor(Math.pow(s, 3) * 100000)
    if (micro == 0) {
        continue;
    }
    model.shutters.push(micro);
}
ko.applyBindings(model)
